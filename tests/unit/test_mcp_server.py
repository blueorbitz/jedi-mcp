"""Unit tests for MCP server implementation."""

import pytest
from pathlib import Path
import tempfile
import sqlite3

from jedi_mcp.mcp_server import (
    sanitize_tool_name,
    generate_tool_description,
    create_mcp_server
)
from jedi_mcp.database import DatabaseManager
from jedi_mcp.models import ContentGroup, PageContent


class TestToolNameSanitization:
    """Tests for tool name sanitization."""
    
    def test_sanitize_simple_name(self):
        """Test sanitization of simple alphanumeric names."""
        assert sanitize_tool_name("Getting Started") == "getting_started"
        assert sanitize_tool_name("API Reference") == "api_reference"
    
    def test_sanitize_special_characters(self):
        """Test sanitization removes special characters."""
        assert sanitize_tool_name("API/Reference") == "apireference"
        assert sanitize_tool_name("Getting-Started!") == "getting-started"
        assert sanitize_tool_name("User@Guide#2024") == "userguide2024"
    
    def test_sanitize_consecutive_underscores(self):
        """Test sanitization removes consecutive underscores."""
        assert sanitize_tool_name("API   Reference") == "api_reference"
        assert sanitize_tool_name("Getting___Started") == "getting_started"
    
    def test_sanitize_leading_trailing_underscores(self):
        """Test sanitization removes leading/trailing underscores."""
        assert sanitize_tool_name("_Getting Started_") == "getting_started"
        assert sanitize_tool_name("__API Reference__") == "api_reference"
    
    def test_sanitize_starts_with_number(self):
        """Test sanitization prepends 'doc_' if name starts with number."""
        assert sanitize_tool_name("2024 Guide") == "doc_2024_guide"
        assert sanitize_tool_name("123") == "doc_123"
    
    def test_sanitize_empty_name(self):
        """Test sanitization returns default for empty names."""
        assert sanitize_tool_name("") == "documentation"
        assert sanitize_tool_name("   ") == "documentation"
        assert sanitize_tool_name("!!!") == "documentation"


class TestToolDescriptionGeneration:
    """Tests for tool description generation."""
    
    def test_generate_simple_description(self):
        """Test generation from simple markdown."""
        markdown = "This is a simple description of the API."
        description = generate_tool_description(markdown, max_length=100)
        assert description == "This is a simple description of the API."
    
    def test_generate_removes_headers(self):
        """Test that markdown headers are removed."""
        markdown = "# API Reference\n\nThis is the API documentation."
        description = generate_tool_description(markdown, max_length=100)
        assert "API Reference" in description
        assert "#" not in description
    
    def test_generate_removes_code_blocks(self):
        """Test that code blocks are removed."""
        markdown = "API docs\n```python\ncode here\n```\nMore text"
        description = generate_tool_description(markdown, max_length=100)
        assert "code here" not in description
        assert "API docs" in description
    
    def test_generate_removes_inline_code(self):
        """Test that inline code is removed."""
        markdown = "Use the `get_user()` function to retrieve users."
        description = generate_tool_description(markdown, max_length=100)
        assert "`" not in description
    
    def test_generate_truncates_long_text(self):
        """Test that long descriptions are truncated."""
        markdown = "This is a very long description " * 20
        description = generate_tool_description(markdown, max_length=50)
        assert len(description) <= 53  # 50 + "..."
        assert description.endswith("...")
    
    def test_generate_empty_markdown(self):
        """Test generation from empty markdown."""
        description = generate_tool_description("", max_length=100)
        assert description == "Documentation content"
        
        description = generate_tool_description("```\ncode\n```", max_length=100)
        assert description == "Documentation content"


class TestMCPServerCreation:
    """Tests for MCP server creation."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        
        yield db_path
        
        # Cleanup
        if db_path.exists():
            db_path.unlink()
    
    @pytest.fixture
    def db_with_content(self, temp_db):
        """Create a database with test content."""
        db_manager = DatabaseManager(temp_db)
        project_name = "test-project"
        
        # Initialize schema
        db_manager.initialize_schema(project_name)
        
        # Add test content groups
        groups = [
            ContentGroup(
                name="Getting Started",
                summary_markdown="# Getting Started\n\nLearn how to get started with our API.",
                pages=[
                    PageContent(
                        url="https://example.com/getting-started",
                        title="Getting Started",
                        content="Getting started content",
                        code_blocks=[]
                    )
                ]
            ),
            ContentGroup(
                name="API Reference",
                summary_markdown="# API Reference\n\nComplete API documentation with examples.",
                pages=[
                    PageContent(
                        url="https://example.com/api",
                        title="API Reference",
                        content="API reference content",
                        code_blocks=[]
                    )
                ]
            )
        ]
        
        for group in groups:
            db_manager.store_content_group(project_name, group, "https://example.com")
        
        return temp_db, db_manager, project_name
    
    def test_create_server_with_valid_project(self, db_with_content):
        """Test creating MCP server with valid project."""
        db_path, db_manager, project_name = db_with_content
        
        mcp = create_mcp_server(project_name, db_manager=db_manager)
        
        assert mcp is not None
        assert mcp.name == f"jedi-mcp-{project_name}"
    
    def test_create_server_registers_tools(self, db_with_content):
        """Test that tools are registered for each content group."""
        db_path, db_manager, project_name = db_with_content
        
        mcp = create_mcp_server(project_name, db_manager=db_manager)
        
        # Get registered tools - this is a dict in FastMCP
        tools_dict = mcp._tool_manager._tools
        
        # Should have 2 legacy content group tools + 3 vector search tools = 5 total
        assert len(tools_dict) == 5
        tool_names = list(tools_dict.keys())
        
        # Legacy content group tools
        assert "getting_started" in tool_names
        assert "api_reference" in tool_names
        
        # New vector search tools
        assert "searchDoc" in tool_names
        assert "loadDoc" in tool_names
        assert "listDoc" in tool_names
    
    def test_create_server_tool_descriptions(self, db_with_content):
        """Test that tool descriptions are generated correctly."""
        db_path, db_manager, project_name = db_with_content
        
        mcp = create_mcp_server(project_name, db_manager=db_manager)
        
        tools_dict = mcp._tool_manager._tools
        
        for tool_name, tool in tools_dict.items():
            assert tool.description is not None
            assert len(tool.description) > 0
            assert "#" not in tool.description  # Headers should be removed
    
    def test_create_server_nonexistent_project(self, temp_db):
        """Test creating server with nonexistent project still works with vector search tools."""
        db_manager = DatabaseManager(temp_db)
        # Initialize schema first
        db_manager.initialize_schema("nonexistent-project")
        
        # Should not raise error anymore since vector search tools are available
        mcp = create_mcp_server("nonexistent-project", db_manager=db_manager)
        
        # Should have 3 vector search tools even without content groups
        tools_dict = mcp._tool_manager._tools
        assert len(tools_dict) == 3
        tool_names = list(tools_dict.keys())
        assert "searchDoc" in tool_names
        assert "loadDoc" in tool_names
        assert "listDoc" in tool_names
    
    def test_create_server_tool_invocation(self, db_with_content):
        """Test that tools can be invoked and return markdown."""
        db_path, db_manager, project_name = db_with_content
        
        mcp = create_mcp_server(project_name, db_manager=db_manager)
        
        # Get a tool from the internal tool manager
        tools_dict = mcp._tool_manager._tools
        tool = tools_dict.get("getting_started")
        assert tool is not None
        
        # Invoke the tool function
        result = tool.fn()
        
        assert result is not None
        assert isinstance(result, str)
        assert "Getting Started" in result
        assert "Learn how to get started" in result
