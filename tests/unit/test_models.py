"""Unit tests for data models."""

import pytest
from jedi_mcp.models import (
    DocumentationLink,
    PageContent,
    ContentGroup,
    CrawlConfig,
    GenerationResult,
)


def test_documentation_link_creation():
    """Test DocumentationLink dataclass creation."""
    link = DocumentationLink(
        url="https://example.com/docs",
        title="Example Docs",
        category="Getting Started"
    )
    assert link.url == "https://example.com/docs"
    assert link.title == "Example Docs"
    assert link.category == "Getting Started"


def test_documentation_link_optional_fields():
    """Test DocumentationLink with optional fields."""
    link = DocumentationLink(url="https://example.com/docs")
    assert link.url == "https://example.com/docs"
    assert link.title is None
    assert link.category is None


def test_page_content_creation():
    """Test PageContent dataclass creation."""
    page = PageContent(
        url="https://example.com/page",
        title="Example Page",
        content="This is the content",
        code_blocks=["print('hello')", "def foo(): pass"]
    )
    assert page.url == "https://example.com/page"
    assert page.title == "Example Page"
    assert page.content == "This is the content"
    assert len(page.code_blocks) == 2


def test_page_content_default_code_blocks():
    """Test PageContent with default empty code_blocks."""
    page = PageContent(
        url="https://example.com/page",
        title="Example Page",
        content="Content"
    )
    assert page.code_blocks == []


def test_content_group_creation():
    """Test ContentGroup dataclass creation."""
    pages = [
        PageContent(url="https://example.com/1", title="Page 1", content="Content 1"),
        PageContent(url="https://example.com/2", title="Page 2", content="Content 2"),
    ]
    group = ContentGroup(
        name="API Reference",
        summary_markdown="# API Reference\n\nThis is the API documentation.",
        pages=pages
    )
    assert group.name == "API Reference"
    assert "# API Reference" in group.summary_markdown
    assert len(group.pages) == 2


def test_content_group_default_pages():
    """Test ContentGroup with default empty pages."""
    group = ContentGroup(
        name="Empty Group",
        summary_markdown="# Empty"
    )
    assert group.pages == []


def test_crawl_config_defaults():
    """Test CrawlConfig with default values."""
    config = CrawlConfig()
    assert config.rate_limit_delay == 0.5
    assert config.max_retries == 3
    assert config.timeout == 30
    assert config.custom_headers is None


def test_crawl_config_custom_values():
    """Test CrawlConfig with custom values."""
    config = CrawlConfig(
        rate_limit_delay=1.0,
        max_retries=5,
        timeout=60,
        custom_headers={"User-Agent": "TestBot"}
    )
    assert config.rate_limit_delay == 1.0
    assert config.max_retries == 5
    assert config.timeout == 60
    assert config.custom_headers == {"User-Agent": "TestBot"}


def test_generation_result_success():
    """Test GenerationResult for successful generation."""
    result = GenerationResult(
        success=True,
        message="MCP server generated successfully",
        database_path="/path/to/db.sqlite",
        project_name="test-project"
    )
    assert result.success is True
    assert "successfully" in result.message
    assert result.database_path == "/path/to/db.sqlite"
    assert result.project_name == "test-project"


def test_generation_result_failure():
    """Test GenerationResult for failed generation."""
    result = GenerationResult(
        success=False,
        message="Failed to generate MCP server"
    )
    assert result.success is False
    assert "Failed" in result.message
    assert result.database_path is None
    assert result.project_name is None
