"""MCP server implementation for exposing documentation as tools."""

import logging
import re
from typing import Optional
from pathlib import Path

from fastmcp import FastMCP

from .database import DatabaseManager
from .models import ContentGroup


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
    # Initialize database manager if not provided
    if db_manager is None:
        db_manager = DatabaseManager(db_path)
    
    # Create FastMCP server
    mcp = FastMCP(f"jedi-mcp-{project_name}")
    
    logger.info(f"Initializing MCP server for project: {project_name}")
    
    try:
        # Query database for all content groups
        content_groups = db_manager.get_all_content_groups(project_name)
        
        if not content_groups:
            logger.warning(f"No content groups found for project: {project_name}")
            raise ValueError(f"Project '{project_name}' not found or has no content groups")
        
        logger.info(f"Found {len(content_groups)} content groups for project: {project_name}")
        
        # Register tools for each content group
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
