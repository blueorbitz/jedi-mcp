"""Navigation extraction using AI to identify documentation links."""

from typing import List
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from strands import Agent

from .models import DocumentationLink


def extract_navigation_links(html_content: str, base_url: str) -> List[DocumentationLink]:
    """
    Extract documentation links from navigation/sidebar elements using AI.
    
    Uses Strands SDK Agent to analyze HTML structure and identify relevant
    documentation links while filtering out external and non-documentation pages.
    
    Args:
        html_content: HTML content of the root documentation page
        base_url: Base URL for resolving relative links
        
    Returns:
        List of DocumentationLink objects with URLs and metadata
        
    Requirements: 2.1, 2.2, 2.3, 2.4
    """
    # Parse HTML to extract navigation elements
    soup = BeautifulSoup(html_content, 'lxml')
    
    # Extract potential navigation elements
    nav_elements = soup.find_all(['nav', 'aside'])
    nav_elements.extend(soup.find_all(class_=lambda x: x and any(
        term in str(x).lower() for term in ['nav', 'sidebar', 'menu', 'toc']
    )))
    
    # Combine navigation HTML
    nav_html = '\n'.join(str(elem) for elem in nav_elements)
    
    if not nav_html.strip():
        # Fallback: use all links if no navigation found
        nav_html = str(soup)
    
    # Create AI agent to analyze navigation
    agent = Agent(
        name="navigation_extractor",
        instructions="""You are a documentation navigation analyzer. Your task is to:
1. Identify links that are part of documentation navigation (nav, sidebar, menu, table of contents)
2. Extract the URL and title for each documentation link
3. Categorize links based on their section or grouping in the navigation
4. Filter out non-documentation links like:
   - Social media links (twitter, github, discord, etc.)
   - Authentication links (login, signup, register)
   - Search functionality
   - External marketing pages
   - Footer links that aren't documentation

Return a JSON array of objects with this structure:
[
  {
    "url": "relative or absolute URL",
    "title": "link text or title",
    "category": "section name if available"
  }
]

Only include links that appear to be documentation content pages."""
    )
    
    # Use agent to extract links
    prompt = f"""Analyze this HTML navigation structure and extract all documentation links.
Base URL: {base_url}

HTML:
{nav_html[:10000]}  # Limit to first 10k chars to avoid token limits

Return only the JSON array of documentation links."""
    
    response = agent.run(prompt)
    
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
        # Try to identify category from parent headings
        category = None
        for heading in nav_elem.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            category = heading.get_text(strip=True)
            break
        
        # Extract all links
        for a_tag in nav_elem.find_all('a', href=True):
            href = a_tag['href']
            title = a_tag.get_text(strip=True) or a_tag.get('title', '')
            
            links.append({
                'url': href,
                'title': title,
                'category': category
            })
    
    return links
