"""Documentation crawler for fetching and extracting content from web pages."""

import asyncio
import logging
from typing import List
from functools import wraps

import httpx
from bs4 import BeautifulSoup

from .models import DocumentationLink, PageContent, CrawlConfig


logger = logging.getLogger(__name__)


def retry_with_backoff(max_retries: int = 3):
    """
    Decorator that retries a function with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except (httpx.RequestError, httpx.HTTPStatusError) as e:
                    if attempt == max_retries - 1:
                        raise
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
            return None
        return wrapper
    return decorator


async def fetch_page_content(
    link: DocumentationLink,
    client: httpx.AsyncClient,
    config: CrawlConfig
) -> PageContent:
    """
    Fetch and extract content from a single documentation page.
    
    Args:
        link: Documentation link to fetch
        client: HTTP client for making requests
        config: Crawl configuration
        
    Returns:
        PageContent with extracted content
        
    Raises:
        httpx.RequestError: On network errors after retries
        httpx.HTTPStatusError: On HTTP error responses after retries
    """
    @retry_with_backoff(max_retries=config.max_retries)
    async def fetch_with_retry():
        response = await client.get(link.url, timeout=config.timeout)
        response.raise_for_status()
        return response.text
    
    try:
        html_content = await fetch_with_retry()
        return extract_content_from_html(html_content, link.url)
    except httpx.RequestError as e:
        error_msg = f"Network error fetching {link.url}: {e}"
        logger.error(error_msg)
        raise
    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error {e.response.status_code} fetching {link.url}"
        logger.error(error_msg)
        raise


def extract_content_from_html(html: str, url: str) -> PageContent:
    """
    Extract main content from HTML, excluding navigation and other non-content elements.
    
    Args:
        html: HTML content to parse
        url: URL of the page (for reference)
        
    Returns:
        PageContent with extracted text and code blocks
    """
    soup = BeautifulSoup(html, 'lxml')
    
    # Extract title from h1 or title tag
    title = ""
    h1_tag = soup.find('h1')
    if h1_tag:
        title = h1_tag.get_text(strip=True)
    else:
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)
    
    # Remove non-content elements
    for element in soup.find_all(['nav', 'footer', 'aside', 'header']):
        element.decompose()
    
    # Extract code blocks before getting text content
    code_blocks = []
    for code_tag in soup.find_all(['pre', 'code']):
        code_text = code_tag.get_text()
        if code_text.strip():
            code_blocks.append(code_text)
    
    # Extract main content
    # Try to find main content area first
    main_content = soup.find('main') or soup.find('article') or soup.find('body')
    
    if main_content:
        content = main_content.get_text(separator='\n', strip=True)
    else:
        content = soup.get_text(separator='\n', strip=True)
    
    return PageContent(
        url=url,
        title=title,
        content=content,
        code_blocks=code_blocks
    )


async def crawl_pages(
    links: List[DocumentationLink],
    config: CrawlConfig
) -> List[PageContent]:
    """
    Crawl documentation pages and extract main content.
    
    Args:
        links: List of documentation links to crawl
        config: Configuration for rate limiting and retries
        
    Returns:
        List of PageContent objects with extracted content
    """
    pages = []
    
    # Set up custom headers if provided
    headers = config.custom_headers or {}
    if 'User-Agent' not in headers:
        headers['User-Agent'] = 'Jedi-MCP Documentation Crawler/0.1.0'
    
    async with httpx.AsyncClient(headers=headers) as client:
        for i, link in enumerate(links):
            try:
                logger.info(f"Crawling {link.url} ({i + 1}/{len(links)})")
                page_content = await fetch_page_content(link, client, config)
                pages.append(page_content)
                
                # Rate limiting: wait between requests (except after the last one)
                if i < len(links) - 1:
                    await asyncio.sleep(config.rate_limit_delay)
                    
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                logger.error(f"Failed to crawl {link.url} after {config.max_retries} retries: {e}")
                # Continue with other pages even if one fails
                continue
    
    return pages
