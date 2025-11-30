"""Unit tests for content processor."""

import pytest
from unittest.mock import Mock, patch
from jedi_mcp.content_processor import process_content, _fallback_grouping
from jedi_mcp.models import PageContent, ContentGroup


class TestProcessContent:
    """Tests for the process_content function."""
    
    def test_process_content_empty_pages(self):
        """Test that empty page list returns empty groups."""
        result = process_content([])
        assert result == []
    
    def test_fallback_grouping_single_page(self):
        """Test fallback grouping with a single page."""
        pages = [
            PageContent(
                url="https://example.com/docs/intro",
                title="Introduction",
                content="Welcome to the documentation",
                code_blocks=[]
            )
        ]
        
        groups = _fallback_grouping(pages)
        assert len(groups) > 0
        assert all('name' in g and 'page_indices' in g for g in groups)
    
    def test_fallback_grouping_multiple_pages(self):
        """Test fallback grouping with multiple pages."""
        pages = [
            PageContent(
                url="https://example.com/docs/intro",
                title="Introduction",
                content="Welcome",
                code_blocks=[]
            ),
            PageContent(
                url="https://example.com/docs/guide",
                title="Guide",
                content="How to use",
                code_blocks=[]
            ),
            PageContent(
                url="https://example.com/api/reference",
                title="API Reference",
                content="API docs",
                code_blocks=[]
            )
        ]
        
        groups = _fallback_grouping(pages)
        assert len(groups) > 0
        
        # Verify all pages are included
        all_indices = []
        for group in groups:
            all_indices.extend(group['page_indices'])
        assert set(all_indices) == set(range(len(pages)))
    
    def test_fallback_grouping_consolidates_many_groups(self):
        """Test that fallback grouping consolidates when there are too many groups."""
        # Create 15 pages with different URL paths
        pages = [
            PageContent(
                url=f"https://example.com/section{i}/page",
                title=f"Page {i}",
                content=f"Content {i}",
                code_blocks=[]
            )
            for i in range(15)
        ]
        
        groups = _fallback_grouping(pages)
        # Should consolidate to avoid too many groups
        assert len(groups) <= 10
    
    @patch('jedi_mcp.content_processor.Agent')
    def test_process_content_with_mocked_agent(self, mock_agent_class):
        """Test process_content with mocked AI agent."""
        # Create mock agent instance
        mock_agent = Mock()
        mock_agent_class.return_value = mock_agent
        
        # Mock grouping response
        grouping_response = Mock()
        grouping_response.__str__ = Mock(return_value='''[
            {
                "name": "getting-started",
                "page_indices": [0],
                "description": "Introduction and setup"
            }
        ]''')
        
        # Mock summary response
        summary_response = Mock()
        summary_response.__str__ = Mock(return_value='''# Getting Started

This is a comprehensive guide to getting started.

## Installation

Install the package using pip:

```bash
pip install example
```

## Quick Start

Here's a simple example:

```python
import example
example.run()
```
''')
        
        # Set up mock to return different responses for different calls
        mock_agent.side_effect = [grouping_response, summary_response]
        
        # Create test pages
        pages = [
            PageContent(
                url="https://example.com/docs/intro",
                title="Introduction",
                content="Welcome to the documentation. This guide will help you get started.",
                code_blocks=["pip install example", "import example\nexample.run()"]
            )
        ]
        
        # Process content
        result = process_content(pages)
        
        # Verify results
        assert len(result) == 1
        assert isinstance(result[0], ContentGroup)
        assert result[0].name == "getting-started"
        assert "Getting Started" in result[0].summary_markdown
        assert len(result[0].pages) == 1
    
    def test_process_content_handles_invalid_json_response(self):
        """Test that process_content handles invalid JSON gracefully."""
        with patch('jedi_mcp.content_processor.Agent') as mock_agent_class:
            mock_agent = Mock()
            mock_agent_class.return_value = mock_agent
            
            # Mock invalid JSON response
            invalid_response = Mock()
            invalid_response.__str__ = Mock(return_value="This is not valid JSON")
            mock_agent.return_value = invalid_response
            
            pages = [
                PageContent(
                    url="https://example.com/docs/intro",
                    title="Introduction",
                    content="Welcome",
                    code_blocks=[]
                )
            ]
            
            # Should fall back to automatic grouping
            result = process_content(pages)
            
            # Should still return groups (using fallback)
            assert len(result) > 0
            assert all(isinstance(g, ContentGroup) for g in result)
