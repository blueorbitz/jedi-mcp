"""Navigation extraction using headless browser and smart DOM parsing.

This module provides navigation extraction with two approaches:
1. Smart DOM parsing (primary) - Fast, no AI needed, works for most doc sites
2. AI-based extraction (fallback) - For complex or unusual navigation structures
"""

import os
import asyncio
from typing import List, Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from strands import Agent
from strands.models.gemini import GeminiModel
from dotenv import load_dotenv

from .models import DocumentationLink

# Load environment variables from .env file
load_dotenv()

# Try to import playwright for browser-based extraction
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


def extract_navigation_links(html_content: str, base_url: str, use_browser: bool = False) -> List[DocumentationLink]:
    """
    Extract documentation links from navigation/sidebar elements.
    
    This function uses smart DOM parsing to extract links from common
    documentation site structures (Docusaurus, generic sidebars, etc.).
    Falls back to AI-based extraction for complex cases.
    
    Args:
        html_content: HTML content of the root documentation page
        base_url: Base URL for resolving relative links
        use_browser: If True, use headless browser to render JavaScript (requires playwright)
        
    Returns:
        List of DocumentationLink objects with URLs and metadata
        
    Requirements: 2.1, 2.2, 2.3, 2.4
    """
    # If browser mode requested and available, use smart extraction
    if use_browser and PLAYWRIGHT_AVAILABLE:
        try:
            return asyncio.run(_extract_with_browser(base_url))
        except Exception as e:
            print(f"⚠️  Browser extraction failed: {e}")
            print("   Falling back to HTML parsing...")
    
    # Use smart DOM parsing on provided HTML
    return _extract_from_html_smart(html_content, base_url)


async def _extract_with_browser(url: str) -> List[DocumentationLink]:
    """Extract navigation using headless browser."""
    from .smart_navigation_extractor import extract_navigation_smart
    return await extract_navigation_smart(url)


def _extract_from_html_smart(html_content: str, base_url: str) -> List[DocumentationLink]:
    """
    Extract links using smart DOM parsing without AI.
    
    This is the primary extraction method that works for most documentation sites.
    """
    soup = BeautifulSoup(html_content, 'lxml')
    
    # Find sidebar
    sidebar = _find_sidebar(soup)
    
    if not sidebar:
        print("⚠️  Warning: Could not find sidebar navigation, using AI fallback")
        return _extract_with_ai(html_content, base_url)
    
    # Extract links using smart parsing
    links = _extract_links_from_sidebar(sidebar, base_url)
    
    return links


def _find_sidebar(soup: BeautifulSoup):
    """Find the main sidebar/navigation element."""
    
    # Try common sidebar patterns
    patterns = [
        # Docusaurus pattern
        {'name': ['aside'], 'class_': lambda x: x and 'sidebar' in str(x).lower()},
        # Generic sidebar patterns
        {'name': ['aside', 'nav'], 'class_': lambda x: x and any(
            term in str(x).lower() for term in ['sidebar', 'side-nav', 'sidenav', 'docs-nav', 'doc-nav']
        )},
        # ID-based patterns
        {'name': ['aside', 'nav', 'div'], 'id': lambda x: x and any(
            term in str(x).lower() for term in ['sidebar', 'navigation', 'nav', 'menu']
        )},
    ]
    
    for pattern in patterns:
        sidebar = soup.find(**pattern)
        if sidebar:
            return sidebar
    
    # Fallback: find any nav or aside
    return soup.find(['nav', 'aside'])


def _extract_links_from_sidebar(sidebar, base_url: str) -> List[DocumentationLink]:
    """Extract links from sidebar with category information."""
    base_domain = urlparse(base_url).netloc
    
    # Check if this is a Docusaurus-style sidebar
    if _is_docusaurus_sidebar(sidebar):
        links = _extract_docusaurus_links(sidebar, base_url, base_domain)
    else:
        # Generic extraction
        links = _extract_generic_links(sidebar, base_url, base_domain)
    
    # Remove duplicates while preserving order
    seen_urls = set()
    unique_links = []
    for link in links:
        if link.url not in seen_urls:
            seen_urls.add(link.url)
            unique_links.append(link)
    
    return unique_links


def _is_docusaurus_sidebar(sidebar) -> bool:
    """Check if this is a Docusaurus-style sidebar."""
    return bool(sidebar.find(class_=lambda x: x and 'theme-doc-sidebar' in str(x)))


def _extract_docusaurus_links(sidebar, base_url: str, base_domain: str) -> List[DocumentationLink]:
    """Extract links from Docusaurus-style sidebar."""
    links = []
    
    # Find all list items
    list_items = sidebar.find_all('li', class_=lambda x: x and 'theme-doc-sidebar-item' in str(x))
    
    current_category = None
    
    for item in list_items:
        # Check if this is a category item
        if 'theme-doc-sidebar-item-category' in ' '.join(item.get('class', [])):
            # This is a category - get the category name
            category_link = item.find('a', class_=lambda x: x and 'menu__link--sublist' in str(x))
            if category_link:
                current_category = category_link.get_text(strip=True)
            
            # Extract nested links under this category
            nested_ul = item.find('ul', class_='menu__list')
            if nested_ul:
                nested_items = nested_ul.find_all('li', recursive=False)
                for nested_item in nested_items:
                    link = nested_item.find('a', href=True)
                    if link:
                        doc_link = _create_doc_link(link, base_url, base_domain, current_category)
                        if doc_link:
                            links.append(doc_link)
        
        # Check if this is a regular link item (not a category)
        elif 'theme-doc-sidebar-item-link' in ' '.join(item.get('class', [])):
            link = item.find('a', href=True, recursive=False)
            if link:
                doc_link = _create_doc_link(link, base_url, base_domain, None)
                if doc_link:
                    links.append(doc_link)
    
    return links


def _extract_generic_links(sidebar, base_url: str, base_domain: str) -> List[DocumentationLink]:
    """Extract links from generic sidebar structure."""
    links = []
    
    # Find all links in the sidebar
    all_links = sidebar.find_all('a', href=True)
    
    for link in all_links:
        # Try to determine category from parent structure
        category = None
        
        # Look for parent heading
        parent = link.find_parent(['li', 'div', 'section'])
        if parent:
            # Look for a heading in the parent or previous siblings
            heading = parent.find_previous(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            if heading:
                heading_text = heading.get_text(strip=True)
                # Only use as category if it's reasonably short
                if len(heading_text) < 50:
                    category = heading_text
        
        doc_link = _create_doc_link(link, base_url, base_domain, category)
        if doc_link:
            links.append(doc_link)
    
    return links


def _create_doc_link(link_tag, base_url: str, base_domain: str, category: Optional[str]) -> Optional[DocumentationLink]:
    """Create a DocumentationLink from an anchor tag."""
    href = link_tag.get('href', '')
    title = link_tag.get_text(strip=True) or link_tag.get('title', '')
    
    # Skip empty or anchor-only links
    if not href or not title or href.startswith('#'):
        return None
    
    # Resolve relative URLs
    absolute_url = urljoin(base_url, href)
    
    # Filter out external links
    link_domain = urlparse(absolute_url).netloc
    if link_domain and link_domain != base_domain:
        return None
    
    # Filter out non-documentation patterns
    url_lower = absolute_url.lower()
    if any(pattern in url_lower for pattern in [
        'twitter.com', 'facebook.com', 'linkedin.com', 'github.com',
        'discord.com', 'slack.com', 'youtube.com',
        '/login', '/signup', '/register', '/auth',
        '/search', '?search=', '/download',
        'mailto:', 'tel:', 'javascript:'
    ]):
        return None
    
    return DocumentationLink(
        url=absolute_url,
        title=title,
        category=category
    )


def _extract_with_ai(html_content: str, base_url: str) -> List[DocumentationLink]:
    """Fallback: Extract navigation using AI when smart parsing fails."""
    
    soup = BeautifulSoup(html_content, 'lxml')
    
    # Extract navigation HTML
    nav_elements = soup.find_all(['nav', 'aside'])
    nav_html = '\n'.join(str(elem) for elem in nav_elements[:3])
    
    if not nav_html.strip():
        nav_html = str(soup)
    
    # Configure Gemini model
    gemini_model = GeminiModel(
        client_args={
            "api_key": os.environ.get("GOOGLE_API_KEY"),
        },
        model_id="gemini-2.5-flash",
        params={
            "temperature": 0.1,
            "max_output_tokens": 8192,
            "top_p": 0.95,
        }
    )
    
    # Create AI agent to analyze navigation
    agent = Agent(
        model=gemini_model,
        system_prompt="""You are a documentation navigation analyzer. Your task is to extract ALL documentation links from the sidebar/navigation menu.

CRITICAL INSTRUCTIONS:
1. Focus ONLY on the main documentation sidebar/navigation menu (usually on the left side)
2. Extract EVERY link in the sidebar navigation, including:
   - Top-level category links
   - All nested/child links under each category
   - Links in collapsible/expandable sections
3. Ignore header navigation, version selectors, and footer links
4. For each link, capture:
   - The URL (href attribute)
   - The link text/title
   - The category/section it belongs to (from parent headings or section names)

WHAT TO EXCLUDE:
- Social media links (twitter, github, discord, etc.)
- Authentication links (login, signup, register)
- Search functionality
- External marketing pages
- Version selector links in the header
- API reference links in the header (unless they're in the main sidebar)

Return a JSON array of objects with this structure:
[
  {
    "url": "relative or absolute URL",
    "title": "link text or title",
    "category": "section/category name from the sidebar"
  }
]

IMPORTANT: Extract ALL links from the sidebar navigation tree, not just top-level items. If you see categories like "Core Concepts", "Advanced Topics", etc., extract all the links under each category."""
    )
    
    # Use agent to extract links
    prompt = f"""Analyze this HTML navigation structure and extract ALL documentation links from the SIDEBAR MENU.

Base URL: {base_url}

INSTRUCTIONS:
1. Look for the main documentation sidebar (usually contains categories like "Getting Started", "Core Concepts", "Advanced Topics", etc.)
2. Extract EVERY link in the sidebar, including nested items under expandable sections
3. For each link, identify which category/section it belongs to
4. Ignore header navigation, version dropdowns, and footer links

HTML Navigation Structure:
{nav_html[:15000]}

Return ONLY a JSON array with ALL sidebar documentation links. No other text."""
    
    response = agent(prompt)
    
    # Parse agent response
    import json
    try:
        # Extract JSON from response
        response_text = str(response)
        # Find JSON array in response
        start_idx = response_text.find('[')
        end_idx = response_text.rfind(']') + 1
        if start_idx >= 0 and end_idx > start_idx:
            json_str = response_text[start_idx:end_idx]
            links_data = json.loads(json_str)
        else:
            links_data = []
    except (json.JSONDecodeError, ValueError):
        # Fallback: extract links manually
        links_data = _fallback_link_extraction(soup, base_url)
    
    # Process and filter links
    base_domain = urlparse(base_url).netloc
    documentation_links = []
    
    for link_data in links_data:
        url = link_data.get('url', '')
        if not url:
            continue
            
        # Resolve relative URLs
        absolute_url = urljoin(base_url, url)
        
        # Filter out external links (different domain)
        link_domain = urlparse(absolute_url).netloc
        if link_domain and link_domain != base_domain:
            continue
        
        # Filter out non-documentation patterns
        url_lower = absolute_url.lower()
        if any(pattern in url_lower for pattern in [
            'twitter.com', 'facebook.com', 'linkedin.com', 'github.com',
            'discord.com', 'slack.com', 'youtube.com',
            '/login', '/signup', '/register', '/auth',
            '/search', '?search=', '/download',
            'mailto:', 'tel:', 'javascript:'
        ]):
            continue
        
        # Create DocumentationLink
        doc_link = DocumentationLink(
            url=absolute_url,
            title=link_data.get('title'),
            category=link_data.get('category')
        )
        documentation_links.append(doc_link)
    
    # Remove duplicates while preserving order
    seen_urls = set()
    unique_links = []
    for link in documentation_links:
        if link.url not in seen_urls:
            seen_urls.add(link.url)
            unique_links.append(link)
    
    return unique_links


def _fallback_link_extraction(soup: BeautifulSoup, base_url: str) -> List[dict]:
    """
    Fallback method to extract links when AI parsing fails.
    
    Args:
        soup: BeautifulSoup parsed HTML
        base_url: Base URL for context
        
    Returns:
        List of dictionaries with url, title, and category
    """
    links = []
    
    # Find all links in navigation elements
    nav_elements = soup.find_all(['nav', 'aside'])
    nav_elements.extend(soup.find_all(class_=lambda x: x and any(
        term in str(x).lower() for term in ['nav', 'sidebar', 'menu', 'toc']
    )))
    
    for nav_elem in nav_elements:
        # Look for hierarchical structure (lists, sections, etc.)
        # Try to find category containers
        categories = nav_elem.find_all(['section', 'div', 'ul'], class_=lambda x: x and any(
            term in str(x).lower() for term in ['category', 'section', 'group']
        ))
        
        if not categories:
            # Fallback: treat each list as a potential category
            categories = nav_elem.find_all(['ul', 'ol'])
        
        if not categories:
            # Last resort: use the whole nav element
            categories = [nav_elem]
        
        for category_elem in categories:
            # Try to identify category name from headings or labels
            category = None
            for heading in category_elem.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'span', 'div'], limit=5):
                text = heading.get_text(strip=True)
                # Check if this looks like a category heading (not too long, not a link)
                if text and len(text) < 50 and not heading.find('a'):
                    category = text
                    break
            
            # Extract all links in this category
            for a_tag in category_elem.find_all('a', href=True):
                href = a_tag['href']
                title = a_tag.get_text(strip=True) or a_tag.get('title', '')
                
                # Skip empty titles or anchors
                if not title or href.startswith('#'):
                    continue
                
                links.append({
                    'url': href,
                    'title': title,
                    'category': category or 'Main Documentation'
                })
    
    return links
