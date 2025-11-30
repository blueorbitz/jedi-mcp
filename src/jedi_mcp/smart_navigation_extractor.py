"""Smart navigation extraction using headless browser and DOM parsing."""

import asyncio
from typing import List, Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from .models import DocumentationLink


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


async def extract_navigation_smart(url: str) -> List[DocumentationLink]:
    """
    Extract documentation links using headless browser and smart DOM parsing.
    
    This approach:
    1. Uses headless browser to render JavaScript
    2. Parses the DOM structure directly without AI
    3. Handles hierarchical navigation with categories
    
    Args:
        url: URL of the documentation root page
        
    Returns:
        List of DocumentationLink objects with URLs and metadata
    """
    # Fetch rendered HTML
    html_content = await fetch_rendered_html(url)
    
    # Parse HTML
    soup = BeautifulSoup(html_content, 'lxml')
    
    # Find sidebar/navigation
    sidebar = _find_sidebar(soup)
    
    if not sidebar:
        print("⚠️  Warning: Could not find sidebar navigation")
        return []
    
    # Extract links from sidebar
    links = _extract_links_from_sidebar(sidebar, url)
    
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
    """
    Extract links from sidebar with category information.
    
    Handles hierarchical structures like:
    - Docusaurus (nested ul/li with category classes)
    - Generic nested lists
    - Flat link lists
    """
    links = []
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
    # Docusaurus uses specific class names
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
