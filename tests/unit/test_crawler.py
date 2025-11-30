"""Unit tests for the documentation crawler."""

import pytest
from bs4 import BeautifulSoup

from jedi_mcp.crawler import extract_content_from_html
from jedi_mcp.models import CrawlConfig, DocumentationLink


class TestExtractContentFromHtml:
    """Tests for HTML content extraction."""
    
    def test_extracts_title_from_h1(self):
        """Test that title is extracted from h1 tag."""
        html = """
        <html>
            <head><title>Page Title</title></head>
            <body>
                <h1>Main Heading</h1>
                <p>Content here</p>
            </body>
        </html>
        """
        result = extract_content_from_html(html, "https://example.com")
        assert result.title == "Main Heading"
    
    def test_extracts_title_from_title_tag_when_no_h1(self):
        """Test that title falls back to title tag when h1 is missing."""
        html = """
        <html>
            <head><title>Page Title</title></head>
            <body>
                <p>Content here</p>
            </body>
        </html>
        """
        result = extract_content_from_html(html, "https://example.com")
        assert result.title == "Page Title"
    
    def test_excludes_navigation_elements(self):
        """Test that nav, footer, aside, and header elements are excluded."""
        html = """
        <html>
            <body>
                <nav>Navigation content</nav>
                <header>Header content</header>
                <aside>Sidebar content</aside>
                <main>
                    <h1>Main Content</h1>
                    <p>This is the main content.</p>
                </main>
                <footer>Footer content</footer>
            </body>
        </html>
        """
        result = extract_content_from_html(html, "https://example.com")
        
        # Main content should be present
        assert "Main Content" in result.content
        assert "This is the main content" in result.content
        
        # Non-content elements should be excluded
        assert "Navigation content" not in result.content
        assert "Header content" not in result.content
        assert "Sidebar content" not in result.content
        assert "Footer content" not in result.content
    
    def test_preserves_code_blocks(self):
        """Test that code blocks are preserved."""
        html = """
        <html>
            <body>
                <h1>Code Example</h1>
                <p>Here's some code:</p>
                <pre><code>def hello():
    print("Hello, world!")</code></pre>
                <p>More text</p>
                <code>inline_code()</code>
            </body>
        </html>
        """
        result = extract_content_from_html(html, "https://example.com")
        
        assert len(result.code_blocks) >= 2
        assert any('def hello()' in block for block in result.code_blocks)
        assert any('inline_code()' in block for block in result.code_blocks)
    
    def test_extracts_main_content_area(self):
        """Test that main content area is prioritized."""
        html = """
        <html>
            <body>
                <div>Random div content</div>
                <main>
                    <h1>Documentation</h1>
                    <p>Main documentation content</p>
                </main>
            </body>
        </html>
        """
        result = extract_content_from_html(html, "https://example.com")
        
        assert "Documentation" in result.content
        assert "Main documentation content" in result.content
    
    def test_handles_empty_html(self):
        """Test that empty HTML is handled gracefully."""
        html = "<html><body></body></html>"
        result = extract_content_from_html(html, "https://example.com")
        
        assert result.url == "https://example.com"
        assert result.title == ""
        assert result.content == ""
        assert result.code_blocks == []
    
    def test_preserves_semantic_structure(self):
        """Test that semantic structure is preserved with newlines."""
        html = """
        <html>
            <body>
                <main>
                    <h1>Title</h1>
                    <p>First paragraph</p>
                    <p>Second paragraph</p>
                    <ul>
                        <li>Item 1</li>
                        <li>Item 2</li>
                    </ul>
                </main>
            </body>
        </html>
        """
        result = extract_content_from_html(html, "https://example.com")
        
        # Content should have structure preserved
        assert "Title" in result.content
        assert "First paragraph" in result.content
        assert "Second paragraph" in result.content
        assert "Item 1" in result.content
        assert "Item 2" in result.content
