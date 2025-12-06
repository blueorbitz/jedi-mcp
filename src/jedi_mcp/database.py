"""Database management for the Jedi-MCP system."""

import sqlite3
from pathlib import Path
from typing import List, Optional
from contextlib import contextmanager

from .models import ContentGroup, PageContent


class DatabaseManager:
    """Manages SQLite database operations for documentation storage."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize the database manager.
        
        Args:
            db_path: Path to the SQLite database file. If None, uses default location.
        """
        if db_path is None:
            db_path = Path.home() / ".jedi-mcp" / "jedi-mcp.db"
        
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def initialize_schema(self, project_name: str) -> None:
        """
        Create database schema if it doesn't exist.
        
        Args:
            project_name: Name of the documentation project
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Create projects table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    root_url TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create content_groups table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS content_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    summary_markdown TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES projects(id),
                    UNIQUE(project_id, name)
                )
            """)
            
            # Create pages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_group_id INTEGER NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    FOREIGN KEY (content_group_id) REFERENCES content_groups(id)
                )
            """)
            
            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_content_groups_project 
                ON content_groups(project_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_pages_group 
                ON pages(content_group_id)
            """)
    
    def _get_or_create_project(self, conn: sqlite3.Connection, project_name: str, root_url: str = "") -> int:
        """
        Get or create a project and return its ID.
        
        Args:
            conn: Database connection
            project_name: Name of the project
            root_url: Root URL of the documentation
            
        Returns:
            Project ID
        """
        cursor = conn.cursor()
        
        # Try to get existing project
        cursor.execute(
            "SELECT id FROM projects WHERE name = ?",
            (project_name,)
        )
        row = cursor.fetchone()
        
        if row:
            return row[0]
        
        # Create new project
        cursor.execute(
            "INSERT INTO projects (name, root_url) VALUES (?, ?)",
            (project_name, root_url)
        )
        return cursor.lastrowid
    
    def store_content_group(self, project_name: str, group: ContentGroup, root_url: str = "") -> int:
        """
        Store a content group and its pages in the database.
        
        Args:
            project_name: Name of the documentation project
            group: ContentGroup to store
            root_url: Root URL of the documentation
            
        Returns:
            ID of the stored content group
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Get or create project
            project_id = self._get_or_create_project(conn, project_name, root_url)
            
            # Insert content group
            cursor.execute(
                """
                INSERT INTO content_groups (project_id, name, summary_markdown)
                VALUES (?, ?, ?)
                """,
                (project_id, group.name, group.summary_markdown)
            )
            content_group_id = cursor.lastrowid
            
            # Insert pages
            for page in group.pages:
                cursor.execute(
                    """
                    INSERT INTO pages (content_group_id, url, title, content)
                    VALUES (?, ?, ?, ?)
                    """,
                    (content_group_id, page.url, page.title, page.content)
                )
            
            return content_group_id
    
    def get_all_content_groups(self, project_name: str) -> List[ContentGroup]:
        """
        Retrieve all content groups for a project.
        
        Args:
            project_name: Name of the documentation project
            
        Returns:
            List of ContentGroup objects
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Get project ID
            cursor.execute(
                "SELECT id FROM projects WHERE name = ?",
                (project_name,)
            )
            project_row = cursor.fetchone()
            
            if not project_row:
                return []
            
            project_id = project_row[0]
            
            # Get all content groups for this project
            cursor.execute(
                """
                SELECT id, name, summary_markdown
                FROM content_groups
                WHERE project_id = ?
                """,
                (project_id,)
            )
            
            content_groups = []
            for row in cursor.fetchall():
                group_id = row[0]
                
                # Get pages for this content group
                cursor.execute(
                    """
                    SELECT url, title, content
                    FROM pages
                    WHERE content_group_id = ?
                    """,
                    (group_id,)
                )
                
                pages = [
                    PageContent(
                        url=page_row[0],
                        title=page_row[1],
                        content=page_row[2],
                        code_blocks=[]  # Code blocks not stored separately
                    )
                    for page_row in cursor.fetchall()
                ]
                
                content_groups.append(
                    ContentGroup(
                        name=row[1],
                        summary_markdown=row[2],
                        pages=pages
                    )
                )
            
            return content_groups
    
    def get_content_group_by_name(self, project_name: str, group_name: str) -> Optional[ContentGroup]:
        """
        Retrieve a specific content group by name.
        
        Args:
            project_name: Name of the documentation project
            group_name: Name of the content group
            
        Returns:
            ContentGroup object or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Get project ID
            cursor.execute(
                "SELECT id FROM projects WHERE name = ?",
                (project_name,)
            )
            project_row = cursor.fetchone()
            
            if not project_row:
                return None
            
            project_id = project_row[0]
            
            # Get content group
            cursor.execute(
                """
                SELECT id, name, summary_markdown
                FROM content_groups
                WHERE project_id = ? AND name = ?
                """,
                (project_id, group_name)
            )
            
            row = cursor.fetchone()
            if not row:
                return None
            
            group_id = row[0]
            
            # Get pages for this content group
            cursor.execute(
                """
                SELECT url, title, content
                FROM pages
                WHERE content_group_id = ?
                """,
                (group_id,)
            )
            
            pages = [
                PageContent(
                    url=page_row[0],
                    title=page_row[1],
                    content=page_row[2],
                    code_blocks=[]  # Code blocks not stored separately
                )
                for page_row in cursor.fetchall()
            ]
            
            return ContentGroup(
                name=row[1],
                summary_markdown=row[2],
                pages=pages
            )
    
    def get_all_projects(self) -> List[dict]:
        """
        Retrieve all projects from the database with metadata.
        
        Returns:
            List of dictionaries containing project information
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Get all projects with content group counts
            cursor.execute(
                """
                SELECT 
                    p.name,
                    p.root_url,
                    p.created_at,
                    COUNT(cg.id) as content_groups_count
                FROM projects p
                LEFT JOIN content_groups cg ON p.id = cg.project_id
                GROUP BY p.id, p.name, p.root_url, p.created_at
                ORDER BY p.created_at DESC
                """
            )
            
            projects = []
            for row in cursor.fetchall():
                projects.append({
                    'name': row[0],
                    'root_url': row[1],
                    'created_at': row[2],
                    'content_groups_count': row[3]
                })
            
            return projects
