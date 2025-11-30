"""Unit tests for CLI validation functions."""

import pytest
from jedi_mcp.cli import validate_url, validate_project_name


class TestURLValidation:
    """Tests for URL validation."""
    
    def test_valid_http_url(self):
        """Test that valid HTTP URLs are accepted."""
        assert validate_url("http://example.com") is True
    
    def test_valid_https_url(self):
        """Test that valid HTTPS URLs are accepted."""
        assert validate_url("https://example.com") is True
        assert validate_url("https://docs.example.com/path") is True
    
    def test_invalid_scheme(self):
        """Test that URLs with invalid schemes are rejected."""
        assert validate_url("ftp://example.com") is False
        assert validate_url("file:///path/to/file") is False
    
    def test_missing_scheme(self):
        """Test that URLs without schemes are rejected."""
        assert validate_url("example.com") is False
        assert validate_url("www.example.com") is False
    
    def test_invalid_url(self):
        """Test that invalid URLs are rejected."""
        assert validate_url("not-a-url") is False
        assert validate_url("") is False
        assert validate_url("http://") is False


class TestProjectNameValidation:
    """Tests for project name validation."""
    
    def test_valid_alphanumeric(self):
        """Test that alphanumeric names are accepted."""
        assert validate_project_name("project123") is True
        assert validate_project_name("MyProject") is True
    
    def test_valid_with_hyphens(self):
        """Test that names with hyphens are accepted."""
        assert validate_project_name("my-project") is True
        assert validate_project_name("project-123") is True
    
    def test_valid_with_underscores(self):
        """Test that names with underscores are accepted."""
        assert validate_project_name("my_project") is True
        assert validate_project_name("project_123") is True
    
    def test_valid_mixed(self):
        """Test that names with mixed valid characters are accepted."""
        assert validate_project_name("my-project_123") is True
        assert validate_project_name("Project-Name_v1") is True
    
    def test_invalid_with_spaces(self):
        """Test that names with spaces are rejected."""
        assert validate_project_name("my project") is False
        assert validate_project_name("project name") is False
    
    def test_invalid_with_special_chars(self):
        """Test that names with special characters are rejected."""
        assert validate_project_name("project!") is False
        assert validate_project_name("my@project") is False
        assert validate_project_name("project#123") is False
        assert validate_project_name("project.name") is False
    
    def test_empty_name(self):
        """Test that empty names are rejected."""
        assert validate_project_name("") is False
