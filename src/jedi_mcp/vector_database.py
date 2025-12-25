"""Vector database management extending SQLite with vector search capabilities."""

import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from contextlib import contextmanager

from .database import DatabaseManager
from .models import (
    EmbeddingConfig, SearchResult, SectionMatch, DocumentSummary, 
    DocumentSection, DocumentMetadata
)


logger = logging.getLogger(__name__)


class VectorDatabaseManager(DatabaseManager):
    """Extends DatabaseManager with vector search capabilities using sqlite-vec."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize the vector database manager.
        
        Args:
            db_path: Path to the SQLite database file. If None, uses default location.
        """
        super().__init__(db_path)
        self._vec_extension_loaded = False
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections with vector extension."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        # Try to load sqlite-vec extension if not already loaded
        if not self._vec_extension_loaded:
            try:
                conn.enable_load_extension(True)
                # Try different possible names for the sqlite-vec extension
                extension_names = ["vec0", "sqlite_vec", "vector"]
                for ext_name in extension_names:
                    try:
                        conn.load_extension(ext_name)
                        self._vec_extension_loaded = True
                        logger.info(f"Loaded sqlite-vec extension '{ext_name}' successfully")
                        break
                    except Exception:
                        continue
                
                if not self._vec_extension_loaded:
                    logger.warning("sqlite-vec extension not available, using fallback similarity search")
            except Exception as e:
                logger.warning(f"Failed to enable extension loading: {e}")
        
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
        Create vector database schema with embedding configuration.
        
        Args:
            project_name: Name of the documentation project
            embedding_config: Configuration for embeddings
        """
        # First initialize base schema
        self.initialize_schema(project_name)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Add embedding configuration columns to projects table if they don't exist
            try:
                cursor.execute("ALTER TABLE projects ADD COLUMN embedding_model TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            try:
                cursor.execute("ALTER TABLE projects ADD COLUMN embedding_dimension INTEGER")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            # Create document embeddings table
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS document_embeddings (
                    slug TEXT PRIMARY KEY,
                    project_id INTEGER NOT NULL,
                    content_group_id INTEGER,
                    title TEXT NOT NULL,
                    summary_text TEXT NOT NULL,
                    category TEXT,
                    keywords TEXT,
                    source_urls TEXT,
                    embedding BLOB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES projects(id),
                    FOREIGN KEY (content_group_id) REFERENCES content_groups(id)
                )
            """)
            
            # Create section embeddings table
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS section_embeddings (
                    section_id TEXT PRIMARY KEY,
                    document_slug TEXT NOT NULL,
                    section_title TEXT NOT NULL,
                    section_content TEXT NOT NULL,
                    section_order INTEGER DEFAULT 0,
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
            
            # Store embedding configuration for this project
            self.store_project_embedding_config(project_name, embedding_config)
    
    def store_project_embedding_config(self, project_name: str, config: EmbeddingConfig) -> None:
        """
        Store embedding configuration for a project.
        
        Args:
            project_name: Name of the project
            config: Embedding configuration to store
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Get or create project first
            project_id = self._get_or_create_project(conn, project_name, "")
            
            # Update project with embedding configuration
            cursor.execute(
                """
                UPDATE projects 
                SET embedding_model = ?, embedding_dimension = ?
                WHERE id = ?
                """,
                (config.model, config.dimension, project_id)
            )
    
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
            
            try:
                cursor.execute(
                    """
                    SELECT embedding_model, embedding_dimension
                    FROM projects
                    WHERE name = ?
                    """,
                    (project_name,)
                )
                
                row = cursor.fetchone()
                if not row or not row[0]:
                    return None
                
                # Determine dimension based on model if not stored
                dimension = row[1]
                if not dimension:
                    dimension_map = {
                        'all-MiniLM-L6-v2': 384,
                        'Qwen3-Embedding-0.6B': 1024
                    }
                    dimension = dimension_map.get(row[0], 384)
                
                return EmbeddingConfig(
                    provider="sentence-transformers",
                    model=row[0],
                    dimension=dimension
                )
            except sqlite3.OperationalError as e:
                if "no such column: embedding_model" in str(e):
                    # This is an older database without vector capabilities
                    return None
                raise
                dimension = dimension_map.get(row[0], 384)
            
            return EmbeddingConfig(
                provider="sentence-transformers",
                model=row[0],
                dimension=dimension
            )
    
    def store_document_embedding(
        self, 
        slug: str, 
        project_name: str,
        title: str,
        summary_text: str,
        embedding: List[float],
        category: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        source_urls: Optional[List[str]] = None,
        content_group_id: Optional[int] = None
    ) -> None:
        """
        Store document embedding in the database.
        
        Args:
            slug: Unique identifier for the document
            project_name: Name of the project
            title: Document title
            summary_text: Document summary text
            embedding: Vector embedding as list of floats
            category: Optional document category
            keywords: Optional list of keywords
            source_urls: Optional list of source URLs
            content_group_id: Optional content group ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Get project ID
            cursor.execute("SELECT id FROM projects WHERE name = ?", (project_name,))
            project_row = cursor.fetchone()
            if not project_row:
                raise ValueError(f"Project '{project_name}' not found")
            
            project_id = project_row[0]
            
            # Convert embedding to blob
            embedding_blob = json.dumps(embedding).encode('utf-8')
            
            # Convert optional lists to JSON strings
            keywords_json = json.dumps(keywords) if keywords else None
            source_urls_json = json.dumps(source_urls) if source_urls else None
            
            # Insert or replace document embedding
            cursor.execute(
                """
                INSERT OR REPLACE INTO document_embeddings 
                (slug, project_id, content_group_id, title, summary_text, category, 
                 keywords, source_urls, embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (slug, project_id, content_group_id, title, summary_text, category,
                 keywords_json, source_urls_json, embedding_blob)
            )
    
    def store_section_embedding(
        self,
        section_id: str,
        document_slug: str,
        section_title: str,
        section_content: str,
        embedding: List[float],
        section_order: int = 0
    ) -> None:
        """
        Store section embedding in the database.
        
        Args:
            section_id: Unique identifier for the section
            document_slug: Slug of the parent document
            section_title: Section title
            section_content: Section content
            embedding: Vector embedding as list of floats
            section_order: Order of section within document
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Convert embedding to blob
            embedding_blob = json.dumps(embedding).encode('utf-8')
            
            # Insert or replace section embedding
            cursor.execute(
                """
                INSERT OR REPLACE INTO section_embeddings 
                (section_id, document_slug, section_title, section_content, 
                 section_order, embedding)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (section_id, document_slug, section_title, section_content,
                 section_order, embedding_blob)
            )
    
    def search_similar_documents(
        self,
        query_embedding: List[float],
        project_name: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 10,
        similarity_threshold: float = 0.0
    ) -> List[SearchResult]:
        """
        Search for similar documents using vector similarity.
        
        Args:
            query_embedding: Query vector embedding
            project_name: Optional project name filter
            category: Optional category filter
            limit: Maximum number of results
            similarity_threshold: Minimum similarity score
            
        Returns:
            List of SearchResult objects ordered by relevance
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Build query with optional filters
            where_conditions = []
            params = []
            
            if project_name:
                where_conditions.append("p.name = ?")
                params.append(project_name)
            
            if category:
                where_conditions.append("de.category = ?")
                params.append(category)
            
            where_clause = ""
            if where_conditions:
                where_clause = "WHERE " + " AND ".join(where_conditions)
            
            # For now, implement cosine similarity manually since sqlite-vec might not be available
            # This is a fallback implementation
            query = f"""
                SELECT 
                    de.slug,
                    de.title,
                    de.category,
                    de.summary_text,
                    de.embedding
                FROM document_embeddings de
                JOIN projects p ON de.project_id = p.id
                {where_clause}
                ORDER BY de.created_at DESC
                LIMIT ?
            """
            
            params.append(limit * 2)  # Get more results for similarity calculation
            cursor.execute(query, params)
            
            results = []
            query_embedding_norm = self._normalize_vector(query_embedding)
            
            for row in cursor.fetchall():
                # Decode embedding
                try:
                    embedding_data = json.loads(row[4].decode('utf-8'))
                    doc_embedding_norm = self._normalize_vector(embedding_data)
                    
                    # Calculate cosine similarity
                    similarity = self._cosine_similarity(query_embedding_norm, doc_embedding_norm)
                    
                    if similarity >= similarity_threshold:
                        # Get section matches for this document
                        section_matches = self._get_section_matches(
                            row[0], query_embedding, similarity_threshold
                        )
                        
                        # Create preview from summary
                        preview = row[3][:200] + "..." if len(row[3]) > 200 else row[3]
                        
                        results.append(SearchResult(
                            slug=row[0],
                            title=row[1],
                            category=row[2] or "General",
                            relevance_score=similarity,
                            content_preview=preview,
                            section_matches=section_matches
                        ))
                except Exception as e:
                    logger.warning(f"Error processing embedding for document {row[0]}: {e}")
                    continue
            
            # Sort by relevance score and limit results
            results.sort(key=lambda x: x.relevance_score, reverse=True)
            return results[:limit]
    
    def _get_section_matches(
        self, 
        document_slug: str, 
        query_embedding: List[float], 
        threshold: float
    ) -> List[SectionMatch]:
        """Get matching sections for a document."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                """
                SELECT section_id, section_title, section_content, embedding
                FROM section_embeddings
                WHERE document_slug = ?
                ORDER BY section_order
                """,
                (document_slug,)
            )
            
            matches = []
            query_embedding_norm = self._normalize_vector(query_embedding)
            
            for row in cursor.fetchall():
                try:
                    embedding_data = json.loads(row[3].decode('utf-8'))
                    section_embedding_norm = self._normalize_vector(embedding_data)
                    
                    similarity = self._cosine_similarity(query_embedding_norm, section_embedding_norm)
                    
                    if similarity >= threshold:
                        snippet = row[2][:150] + "..." if len(row[2]) > 150 else row[2]
                        matches.append(SectionMatch(
                            section_id=row[0],
                            section_title=row[1],
                            content_snippet=snippet,
                            relevance_score=similarity
                        ))
                except Exception as e:
                    logger.warning(f"Error processing section embedding: {e}")
                    continue
            
            return sorted(matches, key=lambda x: x.relevance_score, reverse=True)
    
    def get_document_by_slug(self, slug: str) -> Optional[DocumentSummary]:
        """
        Retrieve a document by its slug.
        
        Args:
            slug: Document slug identifier
            
        Returns:
            DocumentSummary object or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Get document
            cursor.execute(
                """
                SELECT title, category, summary_text, source_urls, created_at
                FROM document_embeddings
                WHERE slug = ?
                """,
                (slug,)
            )
            
            row = cursor.fetchone()
            if not row:
                return None
            
            # Parse source URLs
            source_urls = []
            if row[3]:
                try:
                    source_urls = json.loads(row[3])
                except json.JSONDecodeError:
                    pass
            
            # Get sections
            cursor.execute(
                """
                SELECT section_id, section_title, section_content
                FROM section_embeddings
                WHERE document_slug = ?
                ORDER BY section_order
                """,
                (slug,)
            )
            
            sections = []
            for section_row in cursor.fetchall():
                sections.append(DocumentSection(
                    section_id=section_row[0],
                    title=section_row[1],
                    content=section_row[2],
                    keywords=[]  # Keywords not stored at section level
                ))
            
            return DocumentSummary(
                slug=slug,
                title=row[0],
                category=row[1] or "General",
                full_summary=row[2],
                source_urls=source_urls,
                created_at=row[4],
                sections=sections
            )
    
    def get_similar_slugs(self, slug: str, limit: int = 5) -> List[str]:
        """
        Get similar slugs for suggestion when a slug is not found.
        
        Args:
            slug: The slug that was not found
            limit: Maximum number of suggestions to return
            
        Returns:
            List of similar slugs
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Simple similarity search using LIKE patterns
            # This could be enhanced with more sophisticated string similarity
            slug_lower = slug.lower()
            
            cursor.execute(
                """
                SELECT slug
                FROM document_embeddings
                WHERE LOWER(slug) LIKE ? OR LOWER(title) LIKE ?
                ORDER BY 
                    CASE 
                        WHEN LOWER(slug) = ? THEN 1
                        WHEN LOWER(slug) LIKE ? THEN 2
                        WHEN LOWER(title) LIKE ? THEN 3
                        ELSE 4
                    END
                LIMIT ?
                """,
                (f"%{slug_lower}%", f"%{slug_lower}%", slug_lower, 
                 f"{slug_lower}%", f"%{slug_lower}%", limit)
            )
            
            return [row[0] for row in cursor.fetchall()]
    
    def list_all_documents(self, project_name: str) -> List[DocumentMetadata]:
        """
        List all documents for a project.
        
        Args:
            project_name: Name of the project
            
        Returns:
            List of DocumentMetadata objects
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            try:
                cursor.execute(
                    """
                    SELECT 
                        de.slug,
                        de.title,
                        de.category,
                        de.summary_text,
                        COUNT(se.section_id) as section_count,
                        de.created_at
                    FROM document_embeddings de
                    JOIN projects p ON de.project_id = p.id
                    LEFT JOIN section_embeddings se ON de.slug = se.document_slug
                    WHERE p.name = ?
                    GROUP BY de.slug, de.title, de.category, de.summary_text, de.created_at
                    ORDER BY de.created_at DESC
                    """,
                    (project_name,)
                )
                
                documents = []
                for row in cursor.fetchall():
                    # Create description from summary
                    description = row[3][:100] + "..." if len(row[3]) > 100 else row[3]
                    
                    documents.append(DocumentMetadata(
                        slug=row[0],
                        title=row[1],
                        category=row[2] or "General",
                        description=description,
                        document_count=row[4],  # Actually section count
                        last_updated=row[5]
                    ))
                
                return documents
            except sqlite3.OperationalError as e:
                if "no such table: document_embeddings" in str(e):
                    # This is an older database without vector capabilities
                    return []
                raise
    
    def _normalize_vector(self, vector: List[float]) -> List[float]:
        """Normalize a vector to unit length."""
        import math
        
        magnitude = math.sqrt(sum(x * x for x in vector))
        if magnitude == 0:
            return vector
        return [x / magnitude for x in vector]
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two normalized vectors."""
        if len(vec1) != len(vec2):
            return 0.0
        
        return sum(a * b for a, b in zip(vec1, vec2))