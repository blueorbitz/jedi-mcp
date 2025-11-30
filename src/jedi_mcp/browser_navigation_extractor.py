"""Navigation extraction using headless browser and AI."""

import os
import asyncio
from typing import List, Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, Page
from strands import Agent
from strands.models.gemini import GeminiModel
from dotenv import load_dotenv

from .models import DocumentationLink

# Load environment variables from .env file
load_dotenv()


async def fetch_rendered_html(url: str, wait_for_selector: Optional[str] = None) -> str:
    """
    Fetch HTML content using headless browser to handle JavaScript-rendered content.
    
    Args:
        url: URL to fetch
        wait_for_selector: Optional CSS selector to wait for before extracting HTML
        
    Returns:
        Rendered HTML content
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            # Navigate to the page
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Wait for specific selector if provided
            if wait_for_selector:
                await page.wait_for_selector(wait_for_selector, timeout=10000)
            else:
                # Default: wait a bit for dynamic content to load
                await page.wait_for_timeout(2000)
            
            # Get the rendered HTML
            html_content = await page.content()
            
            return html_content
            
        finally:
            await browser.close()


async def extract_navigation_with_browser(url: str) -> List[DocumentationLink]:
    """
    Extract documentation links using headless browser to render the page first.
    
    Args:
        url: URL of the documentation root page
        
    Returns:
        List of DocumentationLink objects with URLs and metadata
    """
    # Fetch rendered HTML
    html_content = await fetch_rendered_html(url)
    
    # Parse HTML to extract navigation elements
    soup = BeautifulSoup(html_content, 'lxml')
    
    # Extract navigation elements with priority
    nav_elements = []
    
    # 1. Try to find sidebar specifically
    sidebar = soup.find(['aside', 'nav'], class_=lambda x: x and any(
        term in str(x).lower() for term in ['sidebar', 'side-nav', 'sidenav', 'docs-nav', 'doc-nav', 'menu']
    ))
    if sidebar:
        nav_elements.append(sidebar)
    
    # 2. Look for nav/aside elements
    if not nav_elements:
        nav_elements = soup.find_all(['nav', 'aside'])
    
    # 3. Check for elements with navigation-related classes/ids
    if not nav_elements:
        nav_elements.extend(soup.find_all(class_=lambda x: x and any(
            term in str(x).lower() for term in ['nav', 'sidebar', 'menu', 'toc', 'navigation']
        )))
        nav_elements.extend(soup.find_all(id=lambda x: x and any(
            term in str(x).lower() for term in ['nav', 'sidebar', 'menu', 'toc', 'navigation']
        )))
    
    # Combine navigation HTML (limit to first 3 to avoid noise)
    nav_html = '\n'.join(str(elem) for elem in nav_elements[:3])
    
    if not nav_html.strip():
        # Fallback: use all links if no navigation found
        nav_html = str(soup)
    
    # Configure Gemini model
    gemini_model = GeminiModel(
        client_args={
            "api_key": os.environ.get("GOOGLE_API_KEY"),
        },
        model_id="gemini-2.0-flash-exp",
        params={
            "temperature": 0.1,
            "max_output_tokens": 8192,
            "top_p": 0.95,
        }
    )
    
    # Create AI agent to analyze navigation
    agent = Agent(
        model=gemini_model,
        system_prompt="""You are a documentation navigation analyzer. Extract ALL documentation links from the sidebar/navigation menu.

CRITICAL INSTRUCTIONS:
1. Focus on the main documentation sidebar/navigation menu (usually on the left side)
2. Extract EVERY link in the sidebar navigation:
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

Return a JSON array of objects:
[
  {
    "url": "relative or absolute URL",
    "title": "link text or title",
    "category": "section/category name from the sidebar"
  }
]

IMPORTANT: Extract ALL links from the sidebar navigation tree, not just top-level items."""
    )
    
    # Use agent to extract links
    prompt = f"""Analyze this HTML navigation structure and extract ALL documentation links from the SIDEBAR MENU.

Base URL: {url}

INSTRUCTIONS:
1. Look for the main documentation sidebar (categories like "Getting Started", "Core Concepts", etc.)
2. Extract EVERY link in the sidebar, including nested items
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
        start_idx = response_text.find('[')
        end_idx = response_text.rfind(']') + 1
        if start_idx >= 0 and end_idx > start_idx:
            json_str = response_text[start_idx:end_idx]
            links_data = json.loads(json_str)
        else:
            links_data = []
    except (json.JSONDecodeError, ValueError):
        # Fallback: extract links manually
        links_data = _fallback_link_extraction(soup, url)
    
    # Process and filter links
    base_domain = urlparse(url).netloc
    documentation_links = []
    
    for link_data in links_data:
        link_url = link_data.get('url', '')
        if not link_url:
            continue
            
        # Resolve relative URLs
        absolute_url = urljoin(url, link_url)
        
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
        # Look for hierarchical structure
        categories = nav_elem.find_all(['section', 'div', 'ul'], class_=lambda x: x and any(
            term in str(x).lower() for term in ['category', 'section', 'group']
        ))
        
        if not categories:
            categories = nav_elem.find_all(['ul', 'ol'])
        
        if not categories:
            categories = [nav_elem]
        
        for category_elem in categories:
            # Try to identify category name from headings
            category = None
            for heading in category_elem.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'span', 'div'], limit=5):
                text = heading.get_text(strip=True)
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
