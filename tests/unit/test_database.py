"""Unit tests for database operations."""

import pytest
import tempfile
from pathlib import Path

from jedi_mcp.database import DatabaseManager
from jedi_mcp.models import ContentGroup, PageContent


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield db_path


@pytest.fixture
def db_manager(temp_db):
    """Create a DatabaseManager instance with temporary database."""
    return DatabaseManager(db_path=temp_db)


def test_initialize_schema(db_manager):
    """Test database schema initialization."""
    db_manager.initialize_schema("test-project")
    
    # Verify tables were created by attempting to query them
    with db_manager._get_connection() as conn:
        cursor = conn.cursor()
        
        # Check projects table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='projects'")
        assert cursor.fetchone() is not None
        
        # Check content_groups table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='content_groups'")
        assert cursor.fetchone() is not None
        
        # Check pages table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pages'")
        assert cursor.fetchone() is not None


def test_initialize_schema_idempotent(db_manager):
    """Test that initializing schema multiple times doesn't cause errors."""
    db_manager.initialize_schema("test-project")
    db_manager.initialize_schema("test-project")  # Should not raise error


def test_store_and_retrieve_content_group(db_manager):
    """Test storing and retrieving a content group."""
    db_manager.initialize_schema("test-project")
    
    # Create test data
    pages = [
        PageContent(url="https://example.com/1", title="Page 1", content="Content 1"),
        PageContent(url="https://example.com/2", title="Page 2", content="Content 2"),
    ]
    group = ContentGroup(
        name="Test Group",
        summary_markdown="# Test Summary\n\nThis is a test.",
        pages=pages
    )
    
    # Store the group
    group_id = db_manager.store_content_group("test-project", group, "https://example.com")
    assert group_id > 0
    
    # Retrieve the group
    retrieved_group = db_manager.get_content_group_by_name("test-project", "Test Group")
    assert retrieved_group is not None
    assert retrieved_group.name == "Test Group"
    assert retrieved_group.summary_markdown == "# Test Summary\n\nThis is a test."
    assert len(retrieved_group.pages) == 2
    assert retrieved_group.pages[0].url == "https://example.com/1"
    assert retrieved_group.pages[1].url == "https://example.com/2"


def test_get_all_content_groups(db_manager):
    """Test retrieving all content groups for a project."""
    db_manager.initialize_schema("test-project")
    
    # Store multiple groups
    group1 = ContentGroup(
        name="Group 1",
        summary_markdown="# Group 1",
        pages=[PageContent(url="https://example.com/1", title="Page 1", content="Content 1")]
    )
    group2 = ContentGroup(
        name="Group 2",
        summary_markdown="# Group 2",
        pages=[PageContent(url="https://example.com/2", title="Page 2", content="Content 2")]
    )
    
    db_manager.store_content_group("test-project", group1, "https://example.com")
    db_manager.store_content_group("test-project", group2, "https://example.com")
    
    # Retrieve all groups
    all_groups = db_manager.get_all_content_groups("test-project")
    assert len(all_groups) == 2
    assert {g.name for g in all_groups} == {"Group 1", "Group 2"}


def test_get_content_group_nonexistent_project(db_manager):
    """Test retrieving content group from nonexistent project."""
    db_manager.initialize_schema("test-project")
    
    result = db_manager.get_content_group_by_name("nonexistent-project", "Some Group")
    assert result is None


def test_get_content_group_nonexistent_group(db_manager):
    """Test retrieving nonexistent content group."""
    db_manager.initialize_schema("test-project")
    
    result = db_manager.get_content_group_by_name("test-project", "Nonexistent Group")
    assert result is None


def test_get_all_content_groups_empty_project(db_manager):
    """Test retrieving content groups from project with no groups."""
    db_manager.initialize_schema("test-project")
    
    # Create project but don't add any groups
    with db_manager._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO projects (name, root_url) VALUES (?, ?)", ("test-project", "https://example.com"))
    
    all_groups = db_manager.get_all_content_groups("test-project")
    assert all_groups == []


def test_get_all_content_groups_nonexistent_project(db_manager):
    """Test retrieving content groups from nonexistent project."""
    db_manager.initialize_schema("test-project")
    
    all_groups = db_manager.get_all_content_groups("nonexistent-project")
    assert all_groups == []


def test_store_content_group_with_empty_pages(db_manager):
    """Test storing a content group with no pages."""
    db_manager.initialize_schema("test-project")
    
    group = ContentGroup(
        name="Empty Group",
        summary_markdown="# Empty Group",
        pages=[]
    )
    
    group_id = db_manager.store_content_group("test-project", group, "https://example.com")
    assert group_id > 0
    
    retrieved_group = db_manager.get_content_group_by_name("test-project", "Empty Group")
    assert retrieved_group is not None
    assert retrieved_group.name == "Empty Group"
    assert len(retrieved_group.pages) == 0


def test_parameterized_queries_prevent_sql_injection(db_manager):
    """Test that parameterized queries are used (basic check)."""
    db_manager.initialize_schema("test-project")
    
    # Try to inject SQL through group name
    malicious_name = "Test'; DROP TABLE projects; --"
    group = ContentGroup(
        name=malicious_name,
        summary_markdown="# Test",
        pages=[]
    )
    
    db_manager.store_content_group("test-project", group, "https://example.com")
    
    # Verify the projects table still exists
    with db_manager._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='projects'")
        assert cursor.fetchone() is not None
    
    # Verify the group was stored with the malicious string as data
    retrieved = db_manager.get_content_group_by_name("test-project", malicious_name)
    assert retrieved is not None
    assert retrieved.name == malicious_name
