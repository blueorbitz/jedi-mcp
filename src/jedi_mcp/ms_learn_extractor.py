"""Microsoft Learn specific navigation extractor.

This module provides specialized extraction for Microsoft Learn documentation
that handles their collapsible tree navigation structure.
"""

import asyncio
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

from .models import DocumentationLink

# Try to import playwright for browser-based extraction
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


async def extract_ms_learn_navigation(url: str) -> List[DocumentationLink]:
    """
    Extract navigation from Microsoft Learn documentation.
    
    Microsoft Learn uses a collapsible tree structure where sections are
    initially collapsed. This function expands all sections and extracts
    the complete navigation hierarchy.
    
    Args:
        url: URL of the Microsoft Learn documentation page
        
    Returns:
        List of DocumentationLink objects with complete navigation
    """
    if not PLAYWRIGHT_AVAILABLE:
        raise ImportError("Playwright is required for Microsoft Learn extraction")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            print(f"🌐 Loading Microsoft Learn page: {url}")
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Wait for the tree navigation to load
            await page.wait_for_selector('ul.tree.table-of-contents', timeout=10000)
            
            print("🔍 Finding and expanding all collapsible sections...")
            
            # Find all collapsible tree items and expand them
            await _expand_all_tree_sections(page)
            
            # Wait a bit for any dynamic content to load
            await page.wait_for_timeout(2000)
            
            print("📋 Extracting navigation links...")
            
            # Get the rendered HTML after expansion
            html_content = await page.content()
            
            # Parse and extract links
            links = _extract_links_from_expanded_tree(html_content, url)
            
            print(f"✅ Extracted {len(links)} navigation links")
            return links
            
        finally:
            await browser.close()


async def _expand_all_tree_sections(page) -> None:
    """Expand all collapsible sections in the Microsoft Learn tree navigation."""
    
    max_iterations = 5  # Prevent infinite loops
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        print(f"   Expansion iteration {iteration}...")
        
        # Find all collapsed tree items (not just expanders)
        collapsed_items = await page.query_selector_all('li[aria-expanded="false"]')
        
        if not collapsed_items:
            print(f"   No more collapsed sections found")
            break
        
        print(f"   Found {len(collapsed_items)} collapsed sections")
        
        expanded_count = 0
        for i, item in enumerate(collapsed_items):
            try:
                # Find the expander within this item
                expander = await item.query_selector('.tree-expander')
                if expander:
                    print(f"   Expanding section {i+1}/{len(collapsed_items)}")
                    
                    # Click the expander
                    await expander.click()
                    expanded_count += 1
                    
                    # Wait for expansion animation
                    await page.wait_for_timeout(300)
                    
                    # Verify expansion worked
                    aria_expanded = await item.get_attribute('aria-expanded')
                    if aria_expanded == 'true':
                        print(f"     ✓ Successfully expanded")
                    else:
                        print(f"     ⚠ Expansion may have failed")
                        
            except Exception as e:
                print(f"   Warning: Could not expand section {i+1}: {e}")
                continue
        
        if expanded_count == 0:
            print(f"   No sections were expanded in this iteration")
            break
        
        # Wait for any dynamic content to load after expansions
        await page.wait_for_timeout(1000)
    
    # Final verification - check how many sections are now expanded
    final_expanded = await page.query_selector_all('li[aria-expanded="true"]')
    final_collapsed = await page.query_selector_all('li[aria-expanded="false"]')
    
    print(f"   Final state: {len(final_expanded)} expanded, {len(final_collapsed)} still collapsed")
    
    # If there are still collapsed sections, try a different approach
    if final_collapsed:
        print(f"   Attempting alternative expansion method for remaining sections...")
        
        for item in final_collapsed:
            try:
                # Try clicking the entire li element instead of just the expander
                await item.click()
                await page.wait_for_timeout(200)
            except Exception:
                continue
        
        # Final check
        await page.wait_for_timeout(500)
        truly_final_collapsed = await page.query_selector_all('li[aria-expanded="false"]')
        print(f"   After alternative method: {len(truly_final_collapsed)} sections still collapsed")


def _extract_links_from_expanded_tree(html_content: str, base_url: str) -> List[DocumentationLink]:
    """Extract links from the fully expanded Microsoft Learn tree navigation."""
    
    soup = BeautifulSoup(html_content, 'lxml')
    base_domain = urlparse(base_url).netloc
    
    # Find the main tree navigation
    tree = soup.find('ul', class_=lambda x: x and 'tree' in str(x) and 'table-of-contents' in str(x))
    
    if not tree:
        print("⚠️  Warning: Could not find tree navigation")
        return []
    
    links = []
    
    # Extract links recursively from the tree structure
    def extract_from_tree_node(node, parent_category=None, level=0):
        """Recursively extract links from tree nodes."""
        
        # Process direct child list items
        for li in node.find_all('li', role='none', recursive=False):
            # Check if this li contains a direct link
            link = li.find('a', class_='tree-item', recursive=False)
            
            if link and link.get('href'):
                # This is a leaf node with a link
                href = link.get('href', '')
                title = link.get_text(strip=True)
                
                # Skip empty titles or anchor-only links
                if not title or href.startswith('#'):
                    continue
                
                # Resolve relative URLs
                absolute_url = urljoin(base_url, href)
                
                # Filter out external links
                link_domain = urlparse(absolute_url).netloc
                if link_domain and link_domain != base_domain:
                    continue
                
                # Create documentation link
                doc_link = DocumentationLink(
                    url=absolute_url,
                    title=title,
                    category=parent_category
                )
                links.append(doc_link)
            
            # Check if this li has nested content (tree-group)
            nested_group = li.find('ul', class_='tree-group', recursive=False)
            if nested_group:
                # This li might have a category name from a tree-expander
                category_name = parent_category
                
                # Try to get category name from tree-expander span
                expander = li.find('span', class_='tree-expander', recursive=False)
                if expander:
                    # Get text from the expander, excluding the indicator
                    expander_text = expander.get_text(strip=True)
                    # Remove the chevron indicator text if present
                    if expander_text and len(expander_text) > 1:
                        category_name = expander_text
                
                # Recursively process the nested group
                extract_from_tree_node(nested_group, category_name, level + 1)
        
        # Also process tree items that are not in li elements (direct children)
        for tree_item in node.find_all('li', recursive=False):
            # Check if this is a tree item with aria-level (Microsoft Learn pattern)
            if tree_item.get('role') == 'treeitem':
                # This is a category/section header
                expander = tree_item.find('span', class_='tree-expander')
                if expander:
                    category_name = expander.get_text(strip=True)
                    
                    # Look for nested ul with tree-group class
                    nested_ul = tree_item.find('ul', class_='tree-group')
                    if nested_ul:
                        extract_from_tree_node(nested_ul, category_name, level + 1)
    
    # Start extraction from the root tree
    extract_from_tree_node(tree)
    
    # Also extract any direct links in the tree (not in nested groups)
    for link in tree.find_all('a', class_='tree-item', href=True):
        href = link.get('href', '')
        title = link.get_text(strip=True)
        
        # Skip if already processed or invalid
        if not title or href.startswith('#'):
            continue
        
        # Check if this link is already in our list
        absolute_url = urljoin(base_url, href)
        if any(existing.url == absolute_url for existing in links):
            continue
        
        # Filter out external links
        link_domain = urlparse(absolute_url).netloc
        if link_domain and link_domain != base_domain:
            continue
        
        # Try to determine category from parent structure
        category = None
        parent_li = link.find_parent('li')
        if parent_li:
            # Look for a parent with tree-expander
            parent_expander = parent_li.find_parent('li')
            if parent_expander:
                expander_span = parent_expander.find('span', class_='tree-expander')
                if expander_span:
                    category = expander_span.get_text(strip=True)
        
        doc_link = DocumentationLink(
            url=absolute_url,
            title=title,
            category=category or 'Main'
        )
        links.append(doc_link)
    
    # Remove duplicates while preserving order
    seen_urls = set()
    unique_links = []
    for link in links:
        if link.url not in seen_urls:
            seen_urls.add(link.url)
            unique_links.append(link)
    
    return unique_links


def is_microsoft_learn_url(url: str) -> bool:
    """Check if the URL is a Microsoft Learn documentation page."""
    parsed = urlparse(url)
    return parsed.netloc == 'learn.microsoft.com'


async def extract_navigation_with_fallback(url: str) -> List[DocumentationLink]:
    """
    Extract navigation with Microsoft Learn detection and fallback.
    
    Args:
        url: Documentation URL
        
    Returns:
        List of DocumentationLink objects
    """
    if is_microsoft_learn_url(url):
        try:
            return await extract_ms_learn_navigation(url)
        except Exception as e:
            print(f"⚠️  Microsoft Learn extraction failed: {e}")
            print("   Falling back to generic extraction...")
    
    # Fallback to generic extraction
    from .smart_navigation_extractor import extract_navigation_smart
    return await extract_navigation_smart(url)