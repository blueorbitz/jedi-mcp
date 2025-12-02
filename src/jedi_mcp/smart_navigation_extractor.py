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
    
    # Try common sidebar patterns with priority order
    patterns = [
        # Material for MkDocs pattern (div with md-sidebar class)
        {'name': ['div'], 'class_': lambda x: x and 'md-sidebar' in str(x) and 'primary' in str(x)},
        # Docusaurus pattern (aside with sidebar class)
        {'name': ['aside'], 'class_': lambda x: x and 'sidebar' in str(x).lower() and 'banner' not in str(x).lower()},
        # Generic sidebar patterns (div/nav/aside with sidebar-related classes)
        {'name': ['div', 'nav', 'aside'], 'class_': lambda x: x and any(
            term in str(x).lower() for term in ['sidebar', 'side-nav', 'sidenav', 'docs-nav', 'doc-nav']
        ) and 'banner' not in str(x).lower()},
        # ID-based patterns
        {'name': ['aside', 'nav', 'div'], 'id': lambda x: x and any(
            term in str(x).lower() for term in ['sidebar', 'navigation', 'nav', 'menu']
        )},
    ]
    
    for pattern in patterns:
        sidebar = soup.find(**pattern)
        if sidebar:
            # Verify it has a reasonable number of links (at least 5)
            links = sidebar.find_all('a', href=True)
            if len(links) >= 5:
                return sidebar
    
    # Fallback: find any nav or aside (but not banners)
    for elem in soup.find_all(['nav', 'aside']):
        classes = ' '.join(elem.get('class', [])).lower()
        if 'banner' not in classes:
            links = elem.find_all('a', href=True)
            if len(links) >= 5:
                return elem
    
    return None


def _extract_links_from_sidebar(sidebar, base_url: str) -> List[DocumentationLink]:
    """
    Extract links from sidebar with category information.
    
    Handles hierarchical structures like:
    - Docusaurus (nested ul/li with category classes)
    - Material for MkDocs (md-nav structure)
    - Generic nested lists
    - Flat link lists
    """
    links = []
    base_domain = urlparse(base_url).netloc
    
    # Check if this is a Docusaurus-style sidebar
    if _is_docusaurus_sidebar(sidebar):
        links = _extract_docusaurus_links(sidebar, base_url, base_domain)
    # Check if this is a Material for MkDocs sidebar
    elif _is_material_mkdocs_sidebar(sidebar):
        links = _extract_material_mkdocs_links(sidebar, base_url, base_domain)
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


def _is_material_mkdocs_sidebar(sidebar) -> bool:
    """Check if this is a Material for MkDocs sidebar."""
    # Material for MkDocs uses md-sidebar and md-nav classes
    classes = ' '.join(sidebar.get('class', []))
    return 'md-sidebar' in classes or bool(sidebar.find(class_=lambda x: x and 'md-nav' in str(x)))


def _extract_material_mkdocs_links(sidebar, base_url: str, base_domain: str) -> List[DocumentationLink]:
    """Extract links from Material for MkDocs sidebar."""
    links = []
    
    # Find the main navigation
    nav = sidebar.find('nav', class_='md-nav')
    if not nav:
        return links
    
    # Find all top-level list items
    ul = nav.find('ul', class_='md-nav__list')
    if not ul:
        return links
    
    def extract_from_nav_item(item, parent_category=None):
        """Recursively extract links from a nav item."""
        item_links = []
        
        # Check if this is a nested item (has children)
        is_nested = 'md-nav__item--nested' in ' '.join(item.get('class', []))
        
        if is_nested:
            # Get the category name from the link or label
            category_link = item.find('a', class_='md-nav__link', recursive=False)
            if not category_link:
                # Try to find it in the container
                container = item.find('div', class_='md-nav__link')
                if container:
                    category_link = container.find('a', class_='md-nav__link')
            
            category_name = None
            if category_link:
                category_name = category_link.get_text(strip=True)
                # Add the category link itself
                doc_link = _create_doc_link(category_link, base_url, base_domain, parent_category)
                if doc_link:
                    item_links.append(doc_link)
            
            # Find nested navigation
            nested_nav = item.find('nav', class_='md-nav')
            if nested_nav:
                # Find the nested ul inside the nav
                nested_ul = nested_nav.find('ul', class_='md-nav__list')
                if nested_ul:
                    nested_items = nested_ul.find_all('li', class_='md-nav__item', recursive=False)
                    for nested_item in nested_items:
                        item_links.extend(extract_from_nav_item(nested_item, category_name or parent_category))
        else:
            # This is a regular link item
            link = item.find('a', class_='md-nav__link', recursive=False)
            if link:
                doc_link = _create_doc_link(link, base_url, base_domain, parent_category)
                if doc_link:
                    item_links.append(doc_link)
        
        return item_links
    
    # Process all top-level items
    top_level_items = ul.find_all('li', class_='md-nav__item', recursive=False)
    for item in top_level_items:
        links.extend(extract_from_nav_item(item))
    
    return links


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
