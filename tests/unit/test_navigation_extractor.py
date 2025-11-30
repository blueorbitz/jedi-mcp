"""Unit tests for navigation extraction."""

import pytest
from unittest.mock import Mock, patch
from jedi_mcp.navigation_extractor import extract_navigation_links, _fallback_link_extraction
from jedi_mcp.models import DocumentationLink
from bs4 import BeautifulSoup


def test_extract_navigation_links_filters_external_links():
    """Test that external links are filtered out."""
    html = """
    <html>
        <nav>
            <a href="/docs/intro">Introduction</a>
            <a href="https://example.com/docs/guide">Guide</a>
            <a href="https://external.com/page">External</a>
        </nav>
    </html>
    """
    base_url = "https://example.com"
    
    # Mock the Agent to return a simple list
    with patch('jedi_mcp.navigation_extractor.Agent') as MockAgent:
        mock_agent_instance = Mock()
        mock_agent_instance.return_value = """
        [
            {"url": "/docs/intro", "title": "Introduction", "category": null},
            {"url": "https://example.com/docs/guide", "title": "Guide", "category": null},
            {"url": "https://external.com/page", "title": "External", "category": null}
        ]
        """
        MockAgent.return_value = mock_agent_instance
        
        links = extract_navigation_links(html, base_url)
        
        # Should only include links from the same domain
        assert len(links) == 2
        assert all(link.url.startswith("https://example.com") for link in links)


def test_extract_navigation_links_filters_non_documentation():
    """Test that non-documentation links are filtered out."""
    html = """
    <html>
        <nav>
            <a href="/docs/intro">Introduction</a>
            <a href="/login">Login</a>
            <a href="https://twitter.com/example">Twitter</a>
            <a href="/search?q=test">Search</a>
        </nav>
    </html>
    """
    base_url = "https://example.com"
    
    with patch('jedi_mcp.navigation_extractor.Agent') as MockAgent:
        mock_agent_instance = Mock()
        mock_agent_instance.return_value = """
        [
            {"url": "/docs/intro", "title": "Introduction", "category": null},
            {"url": "/login", "title": "Login", "category": null},
            {"url": "https://twitter.com/example", "title": "Twitter", "category": null},
            {"url": "/search?q=test", "title": "Search", "category": null}
        ]
        """
        MockAgent.return_value = mock_agent_instance
        
        links = extract_navigation_links(html, base_url)
        
        # Should only include the documentation link
        assert len(links) == 1
        assert links[0].url == "https://example.com/docs/intro"


def test_extract_navigation_links_resolves_relative_urls():
    """Test that relative URLs are resolved to absolute URLs."""
    html = """
    <html>
        <nav>
            <a href="/docs/intro">Introduction</a>
            <a href="guide.html">Guide</a>
        </nav>
    </html>
    """
    base_url = "https://example.com/docs/"
    
    with patch('jedi_mcp.navigation_extractor.Agent') as MockAgent:
        mock_agent_instance = Mock()
        mock_agent_instance.return_value = """
        [
            {"url": "/docs/intro", "title": "Introduction", "category": null},
            {"url": "guide.html", "title": "Guide", "category": null}
        ]
        """
        MockAgent.return_value = mock_agent_instance
        
        links = extract_navigation_links(html, base_url)
        
        # All URLs should be absolute
        assert all(link.url.startswith("https://") for link in links)


def test_extract_navigation_links_removes_duplicates():
    """Test that duplicate URLs are removed."""
    html = """
    <html>
        <nav>
            <a href="/docs/intro">Introduction</a>
            <a href="/docs/intro">Intro</a>
        </nav>
    </html>
    """
    base_url = "https://example.com"
    
    with patch('jedi_mcp.navigation_extractor.Agent') as MockAgent:
        mock_agent_instance = Mock()
        mock_agent_instance.return_value = """
        [
            {"url": "/docs/intro", "title": "Introduction", "category": null},
            {"url": "/docs/intro", "title": "Intro", "category": null}
        ]
        """
        MockAgent.return_value = mock_agent_instance
        
        links = extract_navigation_links(html, base_url)
        
        # Should only have one link
        assert len(links) == 1


def test_fallback_link_extraction():
    """Test the fallback link extraction when AI parsing fails."""
    html = """
    <html>
        <nav>
            <h2>Getting Started</h2>
            <a href="/docs/intro">Introduction</a>
            <a href="/docs/setup">Setup</a>
        </nav>
    </html>
    """
    soup = BeautifulSoup(html, 'lxml')
    base_url = "https://example.com"
    
    links = _fallback_link_extraction(soup, base_url)
    
    assert len(links) == 2
    assert links[0]['url'] == '/docs/intro'
    assert links[0]['title'] == 'Introduction'
    assert links[0]['category'] == 'Getting Started'


def test_extract_navigation_links_with_categories():
    """Test that categories are preserved from navigation structure."""
    html = """
    <html>
        <nav>
            <a href="/docs/intro">Introduction</a>
        </nav>
    </html>
    """
    base_url = "https://example.com"
    
    with patch('jedi_mcp.navigation_extractor.Agent') as MockAgent:
        mock_agent_instance = Mock()
        mock_agent_instance.return_value = """
        [
            {"url": "/docs/intro", "title": "Introduction", "category": "Getting Started"}
        ]
        """
        MockAgent.return_value = mock_agent_instance
        
        links = extract_navigation_links(html, base_url)
        
        assert len(links) == 1
        assert links[0].category == "Getting Started"


def test_extract_navigation_links_empty_html():
    """Test handling of empty HTML content."""
    html = "<html></html>"
    base_url = "https://example.com"
    
    with patch('jedi_mcp.navigation_extractor.Agent') as MockAgent:
        mock_agent_instance = Mock()
        mock_agent_instance.run.return_value = "[]"
        MockAgent.return_value = mock_agent_instance
        
        links = extract_navigation_links(html, base_url)
        
        assert links == []
