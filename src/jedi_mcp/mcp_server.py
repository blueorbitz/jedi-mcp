"""MCP server implementation for exposing documentation as tools."""

import logging
import re
import json
from typing import Optional, List
from pathlib import Path

from fastmcp import FastMCP

from .database import DatabaseManager
from .vector_database import VectorDatabaseManager
from .embedding_generator import EmbeddingGenerator
from .models import ContentGroup, EmbeddingConfig, SearchResult


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def sanitize_tool_name(name: str) -> str:
    """
    Sanitize content group name for MCP tool name compatibility.
    
    MCP tool names should be alphanumeric with underscores and hyphens.
    
    Args:
        name: Original content group name
        
    Returns:
        Sanitized tool name
    """
    # Convert to lowercase
    sanitized = name.lower()
    
    # Replace spaces with underscores, keep hyphens
    sanitized = re.sub(r'\s+', '_', sanitized)
    
    # Remove special characters except underscores and hyphens
    sanitized = re.sub(r'[^a-z0-9_-]', '', sanitized)
    
    # Remove consecutive underscores
    sanitized = re.sub(r'_+', '_', sanitized)
    
    # Remove leading/trailing underscores and hyphens
    sanitized = sanitized.strip('_-')
    
    # Ensure it starts with a letter (prepend 'doc_' if it doesn't)
    if sanitized and not sanitized[0].isalpha():
        sanitized = f"doc_{sanitized}"
    
    return sanitized or "documentation"


def generate_tool_description(summary_markdown: str, max_length: int = 100) -> str:
    """
    Generate a tool description from summary excerpt.
    
    Args:
        summary_markdown: Full markdown summary
        max_length: Maximum length of description
        
    Returns:
        Tool description string
    """
    # Remove markdown formatting for description
    description = summary_markdown.strip()
    
    # Remove markdown headers
    description = re.sub(r'^#+\s+', '', description, flags=re.MULTILINE)
    
    # Remove code blocks
    description = re.sub(r'```[\s\S]*?```', '', description)
    
    # Remove inline code
    description = re.sub(r'`[^`]+`', '', description)
    
    # Remove extra whitespace
    description = ' '.join(description.split())
    
    # Truncate to max_length
    if len(description) > max_length:
        description = description[:max_length].rsplit(' ', 1)[0] + '...'
    
    return description or "Documentation content"


def create_mcp_server(
    project_name: str,
    db_manager: Optional[DatabaseManager] = None,
    db_path: Optional[Path] = None
) -> FastMCP:
    """
    Create an MCP server for a documentation project.
    
    This function creates an MCP server that dynamically registers tools
    based on content groups stored in the database. Each content group
    becomes an MCP tool that returns its markdown-formatted summary.
    
    Args:
        project_name: Name of the documentation project
        db_manager: Database manager instance (optional, will create if not provided)
        db_path: Path to database file (optional, uses default if not provided)
        
    Returns:
        Configured FastMCP instance
        
    Raises:
        ValueError: If project doesn't exist in database
        Exception: If database query or tool registration fails
    """
    # Initialize vector database manager if not provided or upgrade if needed
    if db_manager is None:
        db_manager = VectorDatabaseManager(db_path)
    elif not isinstance(db_manager, VectorDatabaseManager):
        # Upgrade to VectorDatabaseManager for vector search capabilities
        vector_db_manager = VectorDatabaseManager(db_manager.db_path)
        db_manager = vector_db_manager
    
    # Create FastMCP server
    mcp = FastMCP(f"jedi-mcp-{project_name}")
    
    logger.info(f"Initializing MCP server for project: {project_name}")
    
    try:
        # Initialize embedding generator with project configuration (if available)
        embedding_config = None
        embedding_generator = None
        
        if hasattr(db_manager, 'get_project_embedding_config'):
            try:
                embedding_config = db_manager.get_project_embedding_config(project_name)
                if embedding_config:
                    embedding_generator = EmbeddingGenerator(embedding_config)
                    logger.info(f"Initialized embedding generator with model: {embedding_config.model}")
            except Exception as e:
                logger.warning(f"Failed to initialize embedding generator: {e}")
        
        # Register vector search tools if we have vector capabilities
        if isinstance(db_manager, VectorDatabaseManager):
            register_search_tools(mcp, db_manager, project_name, embedding_generator)
        
        # Query database for all content groups (legacy support)
        content_groups = db_manager.get_all_content_groups(project_name)
        
        if not content_groups:
            logger.warning(f"No content groups found for project: {project_name}")
            # Don't raise error if we have vector search tools - they might still work
            if not isinstance(db_manager, VectorDatabaseManager):
                raise ValueError(f"Project '{project_name}' not found or has no content groups")
        else:
            logger.info(f"Found {len(content_groups)} content groups for project: {project_name}")
            
            # Register tools for each content group (legacy support)
            for group in content_groups:
                try:
                    # Sanitize tool name
                    tool_name = sanitize_tool_name(group.name)
                    
                    # Generate tool description
                    description = generate_tool_description(group.summary_markdown)
                    
                    # Create tool handler function with closure
                    def create_tool_handler(group_name: str, t_name: str):
                        """Create a closure that captures the group name and tool name."""
                        @mcp.tool(name=t_name, description=description)
                        def tool_handler() -> str:
                            """Tool handler that retrieves markdown from database."""
                            try:
                                logger.info(f"Tool invoked: {t_name} (group: {group_name})")
                                
                                # Retrieve content group from database
                                content_group = db_manager.get_content_group_by_name(
                                    project_name,
                                    group_name
                                )
                                
                                if content_group is None:
                                    error_msg = f"Content group '{group_name}' not found"
                                    logger.error(error_msg)
                                    return f"Error: {error_msg}"
                                
                                # Return markdown summary
                                logger.debug(f"Returning markdown for group: {group_name}")
                                return content_group.summary_markdown
                                
                            except Exception as e:
                                error_msg = f"Error retrieving content for '{group_name}': {str(e)}"
                                logger.error(error_msg, exc_info=True)
                                return f"Error: {error_msg}"
                        
                        return tool_handler
                    
                    # Register the tool with FastMCP using the decorator
                    create_tool_handler(group.name, tool_name)
                    
                    logger.info(f"Registered tool: {tool_name} - {description}")
                    
                except Exception as e:
                    logger.error(f"Failed to register tool for group '{group.name}': {str(e)}", exc_info=True)
                    # Continue registering other tools even if one fails
                    continue
        
        logger.info(f"MCP server initialization complete for project: {project_name}")
        return mcp
        
    except Exception as e:
        error_msg = f"Failed to initialize MCP server for project '{project_name}': {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise


def register_search_tools(
    mcp: FastMCP,
    db_manager: VectorDatabaseManager,
    project_name: str,
    embedding_generator: Optional[EmbeddingGenerator]
) -> None:
    """
    Register vector search tools with the MCP server.
    
    Args:
        mcp: FastMCP server instance
        db_manager: Vector database manager
        project_name: Name of the project
        embedding_generator: Embedding generator instance
    """
    
    @mcp.tool(
        name="searchDoc",
        description="Search documentation using semantic similarity and keyword matching"
    )
    def search_documents(
        query: str,
        project: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 5
    ) -> str:
        """
        Search for relevant documentation using semantic similarity.
        
        Args:
            query: Natural language search query
            project: Optional project name filter (defaults to current project)
            category: Optional category filter  
            limit: Maximum number of results (default: 5, max: 20)
            
        Returns:
            JSON string with search results including slugs, titles, scores, and previews
        """
        try:
            logger.info(f"searchDoc invoked with query: '{query}', project: {project}, category: {category}")
            
            # Validate inputs
            if not query or not query.strip():
                return json.dumps({
                    "error": "Query cannot be empty",
                    "results": []
                })
            
            # Limit the maximum number of results
            limit = min(max(1, limit), 20)
            
            # Use provided project or default to current project
            search_project = project or project_name
            
            # Perform semantic search if embedding generator is available
            results = []
            if embedding_generator:
                try:
                    # Generate query embedding
                    query_embedding = embedding_generator.generate_embedding(query.strip())
                    
                    # Perform vector search
                    search_results = db_manager.search_similar_documents(
                        query_embedding=query_embedding,
                        project_name=search_project,
                        category=category,
                        limit=limit,
                        similarity_threshold=0.1  # Low threshold to get more results
                    )
                    
                    # Convert to serializable format
                    results = [
                        {
                            "slug": result.slug,
                            "title": result.title,
                            "category": result.category,
                            "relevance_score": round(result.relevance_score, 3),
                            "content_preview": result.content_preview,
                            "section_matches": [
                                {
                                    "section_id": match.section_id,
                                    "section_title": match.section_title,
                                    "content_snippet": match.content_snippet,
                                    "relevance_score": round(match.relevance_score, 3)
                                }
                                for match in result.section_matches[:3]  # Limit section matches
                            ]
                        }
                        for result in search_results
                    ]
                    
                    logger.info(f"Found {len(results)} semantic search results")
                    
                except Exception as e:
                    logger.error(f"Semantic search failed: {e}")
                    # Fall back to keyword search
                    results = []
            
            # If no semantic results or embedding generator not available, try keyword search
            if not results:
                logger.info("Falling back to keyword-based search")
                results = _perform_keyword_search(
                    db_manager, query, search_project, category, limit
                )
            
            # Format response
            response = {
                "query": query,
                "project": search_project,
                "category": category,
                "total_results": len(results),
                "results": results
            }
            
            if not results:
                response["message"] = "No relevant documents found. Try different keywords or check available categories."
                response["suggestions"] = [
                    "Try broader search terms",
                    "Check spelling and try synonyms",
                    "Use the listDoc tool to see available topics"
                ]
            
            return json.dumps(response, indent=2)
            
        except Exception as e:
            error_msg = f"Search failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return json.dumps({
                "error": error_msg,
                "results": []
            })
    
    @mcp.tool(
        name="loadDoc",
        description="Load full document content by slug identifier"
    )
    def load_document(
        slug: str,
        include_sections: bool = True,
        include_metadata: bool = True
    ) -> str:
        """
        Load complete document summary by slug identifier.
        
        Args:
            slug: Document slug from search results
            include_sections: Include section breakdown (default: True)
            include_metadata: Include source URLs and metadata (default: True)
            
        Returns:
            Complete markdown document with metadata and sections
        """
        try:
            logger.info(f"loadDoc invoked with slug: '{slug}'")
            
            # Validate input
            if not slug or not slug.strip():
                return json.dumps({
                    "error": "Document slug cannot be empty"
                })
            
            # Retrieve document
            document = db_manager.get_document_by_slug(slug.strip())
            
            if not document:
                return json.dumps({
                    "error": f"Document with slug '{slug}' not found",
                    "suggestions": [
                        "Check the slug spelling",
                        "Use searchDoc to find available documents",
                        "Use listDoc to browse all available documents"
                    ]
                })
            
            # Format response
            response = {
                "slug": document.slug,
                "title": document.title,
                "category": document.category,
                "full_summary": document.full_summary
            }
            
            if include_metadata:
                response["metadata"] = {
                    "source_urls": document.source_urls,
                    "created_at": document.created_at,
                    "category": document.category
                }
            
            if include_sections and document.sections:
                response["sections"] = [
                    {
                        "section_id": section.section_id,
                        "title": section.title,
                        "content": section.content,
                        "keywords": section.keywords
                    }
                    for section in document.sections
                ]
            
            logger.info(f"Successfully loaded document: {document.title}")
            return json.dumps(response, indent=2)
            
        except Exception as e:
            error_msg = f"Failed to load document: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return json.dumps({
                "error": error_msg
            })
    
    @mcp.tool(
        name="listDoc",
        description="List available documentation topics and categories"
    )
    def list_documents(
        project: Optional[str] = None,
        category: Optional[str] = None,
        sort_by: str = "title"
    ) -> str:
        """
        List all available documentation topics with metadata.
        
        Args:
            project: Optional project name filter (defaults to current project)
            category: Optional category filter
            sort_by: Sort order - title, category, or date (default: title)
            
        Returns:
            Structured list of documents with categories and descriptions
        """
        try:
            logger.info(f"listDoc invoked with project: {project}, category: {category}, sort_by: {sort_by}")
            
            # Use provided project or default to current project
            list_project = project or project_name
            
            # Get all documents for the project
            documents = db_manager.list_all_documents(list_project)
            
            # Apply category filter if specified
            if category:
                documents = [doc for doc in documents if doc.category.lower() == category.lower()]
            
            # Sort documents
            if sort_by == "category":
                documents.sort(key=lambda x: (x.category, x.title))
            elif sort_by == "date":
                documents.sort(key=lambda x: x.last_updated, reverse=True)
            else:  # default to title
                documents.sort(key=lambda x: x.title)
            
            # Group by category
            categories = {}
            for doc in documents:
                cat = doc.category
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append({
                    "slug": doc.slug,
                    "title": doc.title,
                    "description": doc.description,
                    "last_updated": doc.last_updated,
                    "section_count": doc.document_count
                })
            
            # Format response
            response = {
                "project": list_project,
                "category_filter": category,
                "sort_by": sort_by,
                "total_documents": len(documents),
                "total_categories": len(categories),
                "categories": []
            }
            
            # Add category information
            for cat_name, cat_docs in categories.items():
                response["categories"].append({
                    "name": cat_name,
                    "document_count": len(cat_docs),
                    "documents": cat_docs
                })
            
            # Sort categories by name
            response["categories"].sort(key=lambda x: x["name"])
            
            if not documents:
                response["message"] = f"No documents found for project '{list_project}'"
                if category:
                    response["message"] += f" in category '{category}'"
                response["suggestions"] = [
                    "Check if the project name is correct",
                    "Try without category filter",
                    "Ensure documents have been generated for this project"
                ]
            
            logger.info(f"Listed {len(documents)} documents in {len(categories)} categories")
            return json.dumps(response, indent=2)
            
        except Exception as e:
            error_msg = f"Failed to list documents: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return json.dumps({
                "error": error_msg
            })


def _perform_keyword_search(
    db_manager: VectorDatabaseManager,
    query: str,
    project_name: str,
    category: Optional[str],
    limit: int
) -> List[dict]:
    """
    Perform keyword-based search as fallback.
    
    Args:
        db_manager: Database manager
        query: Search query
        project_name: Project name
        category: Optional category filter
        limit: Maximum results
        
    Returns:
        List of search result dictionaries
    """
    try:
        # Simple keyword search in document titles and summaries
        with db_manager._get_connection() as conn:
            cursor = conn.cursor()
            
            # Build search query
            search_terms = query.lower().split()
            where_conditions = ["p.name = ?"]
            params = [project_name]
            
            if category:
                where_conditions.append("de.category = ?")
                params.append(category)
            
            # Add keyword search conditions
            keyword_conditions = []
            for term in search_terms:
                keyword_conditions.append(
                    "(LOWER(de.title) LIKE ? OR LOWER(de.summary_text) LIKE ?)"
                )
                params.extend([f"%{term}%", f"%{term}%"])
            
            if keyword_conditions:
                where_conditions.append("(" + " OR ".join(keyword_conditions) + ")")
            
            where_clause = "WHERE " + " AND ".join(where_conditions)
            
            query_sql = f"""
                SELECT 
                    de.slug,
                    de.title,
                    de.category,
                    de.summary_text
                FROM document_embeddings de
                JOIN projects p ON de.project_id = p.id
                {where_clause}
                ORDER BY de.created_at DESC
                LIMIT ?
            """
            
            params.append(limit)
            cursor.execute(query_sql, params)
            
            results = []
            for row in cursor.fetchall():
                preview = row[3][:200] + "..." if len(row[3]) > 200 else row[3]
                
                results.append({
                    "slug": row[0],
                    "title": row[1],
                    "category": row[2] or "General",
                    "relevance_score": 0.5,  # Default score for keyword search
                    "content_preview": preview,
                    "section_matches": []
                })
            
            return results
            
    except Exception as e:
        logger.error(f"Keyword search failed: {e}")
        return []


def run_mcp_server(
    project_name: str,
    db_path: Optional[Path] = None,
    transport: str = "stdio",
    host: str = "localhost",
    port: int = 8000
) -> None:
    """
    Run the MCP server for a documentation project.
    
    This is a convenience function that creates and runs the MCP server
    using the specified transport.
    
    Args:
        project_name: Name of the documentation project
        db_path: Path to database file (optional, uses default if not provided)
        transport: Transport type - "stdio" or "sse" (default: "stdio")
        host: Host to bind to for SSE transport (default: "localhost")
        port: Port to bind to for SSE transport (default: 8000)
    """
    try:
        logger.info(f"Starting MCP server for project: {project_name}")
        logger.info(f"Transport: {transport}")
        
        # Create server
        mcp = create_mcp_server(project_name, db_path=db_path)
        
        # Run server with specified transport
        if transport == "sse":
            logger.info(f"Starting SSE server on {host}:{port}")
            mcp.run(transport="sse", host=host, port=port)
        else:
            logger.info("Starting stdio server")
            mcp.run()
            
    except Exception as e:
        logger.error(f"Failed to run MCP server: {str(e)}", exc_info=True)
        raise
