"""Vector database management for the Jedi-MCP system."""

import sqlite3
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from .database import DatabaseManager
from .models import EmbeddingConfig, SearchResult, DocumentSummary, DocumentMetadata, SectionMatch, DocumentSection


class VectorDatabaseManager(DatabaseManager):
    """Extends DatabaseManager with vector search capabilities using sqlite-vec."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize the vector database manager.
        
        Args:
            db_path: Path to the SQLite database file. If None, uses default location.
        """
        super().__init__(db_path)
        self._vector_extension_loaded = False
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections with vector extension."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        # Try to load sqlite-vec extension if not already attempted
        if not hasattr(self, '_extension_load_attempted'):
            self._extension_load_attempted = True
            try:
                conn.enable_load_extension(True)
                # Try different possible extension names
                extension_names = ["vec0", "sqlite_vec", "vector"]
                for ext_name in extension_names:
                    try:
                        conn.load_extension(ext_name)
                        self._vector_extension_loaded = True
                        print(f"Successfully loaded vector extension: {ext_name}")
                        break
                    except sqlite3.OperationalError:
                        continue
                
                if not self._vector_extension_loaded:
                    print("Warning: Could not load sqlite-vec extension.")
                    print("Vector search will use fallback implementation.")
                    
            except sqlite3.OperationalError as e:
                print(f"Warning: Extension loading not supported: {e}")
                print("Vector search will use fallback implementation.")
        
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def initialize_vector_schema(self, project_name: str, embedding_config: EmbeddingConfig) -> None:
        """
        Initialize vector database schema with embedding configuration.
        
        Args:
            project_name: Name of the documentation project
            embedding_config: Configuration for embeddings
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # First initialize the base schema
            self.initialize_schema(project_name)
            
            # Check if embedding columns exist, add them if they don't
            cursor.execute("PRAGMA table_info(projects)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'embedding_model' not in columns:
                cursor.execute("""
                    ALTER TABLE projects ADD COLUMN embedding_model TEXT DEFAULT NULL
                """)
            
            if 'embedding_dimension' not in columns:
                cursor.execute("""
                    ALTER TABLE projects ADD COLUMN embedding_dimension INTEGER DEFAULT NULL
                """)
            
            # Store embedding configuration for this project
            self.store_project_embedding_config(project_name, embedding_config)
            
            # Create document embeddings table with dynamic dimension
            try:
                cursor.execute(f"""
                    CREATE VIRTUAL TABLE IF NOT EXISTS document_embeddings USING vec0(
                        slug TEXT PRIMARY KEY,
                        project_id INTEGER,
                        content_group_id INTEGER,
                        title TEXT,
                        summary_text TEXT,
                        category TEXT,
                        keywords TEXT,
                        source_urls TEXT,
                        embedding({embedding_config.dimension}),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            except sqlite3.OperationalError:
                # Fallback table without vector extension
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS document_embeddings (
                        slug TEXT PRIMARY KEY,
                        project_id INTEGER,
                        content_group_id INTEGER,
                        title TEXT,
                        summary_text TEXT,
                        category TEXT,
                        keywords TEXT,
                        source_urls TEXT,
                        embedding BLOB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (project_id) REFERENCES projects(id),
                        FOREIGN KEY (content_group_id) REFERENCES content_groups(id)
                    )
                """)
            
            # Create section embeddings table with dynamic dimension
            try:
                cursor.execute(f"""
                    CREATE VIRTUAL TABLE IF NOT EXISTS section_embeddings USING vec0(
                        section_id TEXT PRIMARY KEY,
                        document_slug TEXT,
                        section_title TEXT,
                        section_content TEXT,
                        section_order INTEGER,
                        embedding({embedding_config.dimension}),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            except sqlite3.OperationalError:
                # Fallback table without vector extension
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS section_embeddings (
                        section_id TEXT PRIMARY KEY,
                        document_slug TEXT,
                        section_title TEXT,
                        section_content TEXT,
                        section_order INTEGER,
                        embedding BLOB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (document_slug) REFERENCES document_embeddings(slug)
                    )
                """)
            
            # Create indexes for better performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_embeddings_project 
                ON document_embeddings(project_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_embeddings_category 
                ON document_embeddings(category)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_section_embeddings_document 
                ON section_embeddings(document_slug)
            """)
    
    def store_project_embedding_config(self, project_name: str, config: EmbeddingConfig) -> None:
        """
        Store embedding configuration for a project.
        
        Args:
            project_name: Name of the project
            config: Embedding configuration to store
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Ensure project exists first
            project_id = self._get_or_create_project(conn, project_name, "")
            
            # Update the project with embedding configuration
            cursor.execute("""
                UPDATE projects 
                SET embedding_model = ?, embedding_dimension = ?
                WHERE name = ?
            """, (config.model, config.dimension, project_name))
    
    def get_project_embedding_config(self, project_name: str) -> Optional[EmbeddingConfig]:
        """
        Retrieve embedding configuration for a project.
        
        Args:
            project_name: Name of the project
            
        Returns:
            EmbeddingConfig object or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT embedding_model, embedding_dimension
                FROM projects
                WHERE name = ?
            """, (project_name,))
            
            row = cursor.fetchone()
            if not row or not row[0]:
                return None
            
            return EmbeddingConfig(
                provider="sentence-transformers",
                model=row[0],
                dimension=row[1] if row[1] is not None else 384
            )
    
    def store_document_embedding(self, slug: str, project_name: str, content_group_id: int, 
                                title: str, summary_text: str, category: str, 
                                keywords: List[str], source_urls: List[str], 
                                embedding: List[float]) -> None:
        """
        Store a document embedding in the vector database.
        
        Args:
            slug: Unique identifier for the document
            project_name: Name of the project
            content_group_id: ID of the content group
            title: Document title
            summary_text: Document summary text
            category: Document category
            keywords: List of keywords
            source_urls: List of source URLs
            embedding: Vector embedding
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Get project ID
            cursor.execute("SELECT id FROM projects WHERE name = ?", (project_name,))
            project_row = cursor.fetchone()
            if not project_row:
                raise ValueError(f"Project '{project_name}' not found")
            
            project_id = project_row[0]
            
            # Convert lists to JSON strings
            keywords_json = json.dumps(keywords)
            source_urls_json = json.dumps(source_urls)
            
            # Store document embedding
            if self._vector_extension_loaded:
                # Use vector extension
                embedding_blob = json.dumps(embedding).encode()
                cursor.execute("""
                    INSERT OR REPLACE INTO document_embeddings 
                    (slug, project_id, content_group_id, title, summary_text, category, 
                     keywords, source_urls, embedding)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (slug, project_id, content_group_id, title, summary_text, category,
                      keywords_json, source_urls_json, embedding_blob))
            else:
                # Fallback without vector extension
                embedding_blob = json.dumps(embedding).encode()
                cursor.execute("""
                    INSERT OR REPLACE INTO document_embeddings 
                    (slug, project_id, content_group_id, title, summary_text, category, 
                     keywords, source_urls, embedding)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (slug, project_id, content_group_id, title, summary_text, category,
                      keywords_json, source_urls_json, embedding_blob))
    
    def store_section_embedding(self, section_id: str, document_slug: str, 
                               section_title: str, section_content: str, 
                               section_order: int, embedding: List[float]) -> None:
        """
        Store a section embedding in the vector database.
        
        Args:
            section_id: Unique identifier for the section
            document_slug: Slug of the parent document
            section_title: Section title
            section_content: Section content
            section_order: Order of section within document
            embedding: Vector embedding
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            if self._vector_extension_loaded:
                # Use vector extension
                embedding_blob = json.dumps(embedding).encode()
                cursor.execute("""
                    INSERT OR REPLACE INTO section_embeddings 
                    (section_id, document_slug, section_title, section_content, 
                     section_order, embedding)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (section_id, document_slug, section_title, section_content,
                      section_order, embedding_blob))
            else:
                # Fallback without vector extension
                embedding_blob = json.dumps(embedding).encode()
                cursor.execute("""
                    INSERT OR REPLACE INTO section_embeddings 
                    (section_id, document_slug, section_title, section_content, 
                     section_order, embedding)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (section_id, document_slug, section_title, section_content,
                      section_order, embedding_blob))
    
    def search_similar_documents(self, query_embedding: List[float], project_name: str,
                                category: Optional[str] = None, limit: int = 10) -> List[SearchResult]:
        """
        Search for similar documents using vector similarity.
        
        Args:
            query_embedding: Vector embedding of the search query
            project_name: Name of the project to search within
            category: Optional category filter
            limit: Maximum number of results to return
            
        Returns:
            List of SearchResult objects
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Get project ID
            cursor.execute("SELECT id FROM projects WHERE name = ?", (project_name,))
            project_row = cursor.fetchone()
            if not project_row:
                return []
            
            project_id = project_row[0]
            
            if self._vector_extension_loaded:
                # Use vector similarity search
                query_blob = json.dumps(query_embedding).encode()
                
                if category:
                    cursor.execute("""
                        SELECT slug, title, category, summary_text, 
                               vec_distance_cosine(embedding, ?) as distance
                        FROM document_embeddings
                        WHERE project_id = ? AND category = ?
                        ORDER BY distance ASC
                        LIMIT ?
                    """, (query_blob, project_id, category, limit))
                else:
                    cursor.execute("""
                        SELECT slug, title, category, summary_text,
                               vec_distance_cosine(embedding, ?) as distance
                        FROM document_embeddings
                        WHERE project_id = ?
                        ORDER BY distance ASC
                        LIMIT ?
                    """, (query_blob, project_id, limit))
            else:
                # Fallback to simple text search
                if category:
                    cursor.execute("""
                        SELECT slug, title, category, summary_text, 0.5 as distance
                        FROM document_embeddings
                        WHERE project_id = ? AND category = ?
                        LIMIT ?
                    """, (project_id, category, limit))
                else:
                    cursor.execute("""
                        SELECT slug, title, category, summary_text, 0.5 as distance
                        FROM document_embeddings
                        WHERE project_id = ?
                        LIMIT ?
                    """, (project_id, limit))
            
            results = []
            for row in cursor.fetchall():
                # Convert distance to relevance score (1 - distance)
                relevance_score = max(0.0, 1.0 - row[4])
                
                # Create preview from summary text (first 200 chars)
                content_preview = row[3][:200] + "..." if len(row[3]) > 200 else row[3]
                
                results.append(SearchResult(
                    slug=row[0],
                    title=row[1],
                    category=row[2],
                    relevance_score=relevance_score,
                    content_preview=content_preview
                ))
            
            return results
    
    def get_document_by_slug(self, slug: str) -> Optional[DocumentSummary]:
        """
        Retrieve a document by its slug.
        
        Args:
            slug: Document slug
            
        Returns:
            DocumentSummary object or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT slug, title, category, summary_text, source_urls, created_at
                FROM document_embeddings
                WHERE slug = ?
            """, (slug,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            # Parse source URLs from JSON
            source_urls = json.loads(row[4]) if row[4] else []
            
            # Get sections for this document
            cursor.execute("""
                SELECT section_id, section_title, section_content
                FROM section_embeddings
                WHERE document_slug = ?
                ORDER BY section_order
            """, (slug,))
            
            sections = []
            for section_row in cursor.fetchall():
                sections.append(DocumentSection(
                    section_id=section_row[0],
                    title=section_row[1],
                    content=section_row[2]
                ))
            
            return DocumentSummary(
                slug=row[0],
                title=row[1],
                category=row[2],
                full_summary=row[3],
                source_urls=source_urls,
                created_at=row[5],
                sections=sections
            )
    
    def list_all_documents(self, project_name: str, category: Optional[str] = None) -> List[DocumentMetadata]:
        """
        List all documents for a project.
        
        Args:
            project_name: Name of the project
            category: Optional category filter
            
        Returns:
            List of DocumentMetadata objects
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Get project ID
            cursor.execute("SELECT id FROM projects WHERE name = ?", (project_name,))
            project_row = cursor.fetchone()
            if not project_row:
                return []
            
            project_id = project_row[0]
            
            if category:
                cursor.execute("""
                    SELECT slug, title, category, summary_text, created_at
                    FROM document_embeddings
                    WHERE project_id = ? AND category = ?
                    ORDER BY title
                """, (project_id, category))
            else:
                cursor.execute("""
                    SELECT slug, title, category, summary_text, created_at
                    FROM document_embeddings
                    WHERE project_id = ?
                    ORDER BY category, title
                """, (project_id,))
            
            documents = []
            for row in cursor.fetchall():
                # Create description from summary (first 100 chars)
                description = row[3][:100] + "..." if len(row[3]) > 100 else row[3]
                
                documents.append(DocumentMetadata(
                    slug=row[0],
                    title=row[1],
                    category=row[2],
                    description=description,
                    document_count=1,  # Each document is counted as 1
                    last_updated=row[4]
                ))
            
            return documents