"""Command-line interface for Jedi-MCP."""

import asyncio
import logging
import re
import signal
import sys
from pathlib import Path
from urllib.parse import urlparse

import click
import httpx

from .models import CrawlConfig, GenerationResult
from .database import DatabaseManager
from .navigation_extractor import extract_navigation_links
from .crawler import crawl_pages
from .content_processor import process_content
from .mcp_server import run_mcp_server


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def validate_url(url: str) -> bool:
    """
    Validate URL format (http/https scheme).
    
    Args:
        url: URL to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        parsed = urlparse(url)
        return parsed.scheme in ('http', 'https') and bool(parsed.netloc)
    except Exception:
        return False


def validate_project_name(name: str) -> bool:
    """
    Validate project name (alphanumeric, hyphens, underscores only).
    
    Args:
        name: Project name to validate
        
    Returns:
        True if valid, False otherwise
    """
    # Must contain only alphanumeric characters, hyphens, and underscores
    # Must not be empty
    pattern = r'^[a-zA-Z0-9_-]+$'
    return bool(re.match(pattern, name))


async def generate_mcp_server_async(
    url: str,
    name: str,
    config: CrawlConfig,
    db_path: Path
) -> GenerationResult:
    """
    Generate an MCP server from a documentation URL (async implementation).
    
    Args:
        url: Root documentation URL to process
        name: Project name for the generated MCP server
        config: Configuration for crawling behavior
        db_path: Path to the database file
        
    Returns:
        GenerationResult containing status and output path
    """
    try:
        # Initialize database
        click.echo("📦 Initializing database...")
        db_manager = DatabaseManager(db_path)
        db_manager.initialize_schema(name)
        
        # Step 1: Extract navigation links
        click.echo(f"🔍 Extracting navigation links from {url}...")
        
        async with httpx.AsyncClient(timeout=config.timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            html_content = response.text
        
        links = extract_navigation_links(html_content, url)
        
        if not links:
            return GenerationResult(
                success=False,
                message="No documentation links found. Please check the URL.",
                database_path=None,
                project_name=name
            )
        
        click.echo(f"✓ Found {len(links)} documentation links")
        
        # Step 2: Crawl pages
        click.echo(f"📥 Crawling {len(links)} pages...")
        with click.progressbar(
            length=len(links),
            label='Crawling pages',
            show_pos=True
        ) as bar:
            pages = await crawl_pages(links, config)
            bar.update(len(pages))
        
        if not pages:
            return GenerationResult(
                success=False,
                message="Failed to crawl any pages. Please check the URL and network connection.",
                database_path=None,
                project_name=name
            )
        
        click.echo(f"✓ Successfully crawled {len(pages)} pages")
        
        # Step 3: Process content and group
        click.echo("🤖 Processing content and generating summaries (this may take a minute)...")
        content_groups = process_content(pages)
        
        if not content_groups:
            return GenerationResult(
                success=False,
                message="Failed to process content into groups.",
                database_path=None,
                project_name=name
            )
        
        click.echo(f"✓ Created {len(content_groups)} content groups")
        
        # Step 4: Store in database
        click.echo("💾 Storing content in database...")
        for group in content_groups:
            db_manager.store_content_group(name, group, url)
        
        click.echo(f"✓ Stored {len(content_groups)} content groups")
        
        return GenerationResult(
            success=True,
            message=f"Successfully generated MCP server for '{name}'",
            database_path=str(db_path),
            project_name=name
        )
        
    except httpx.HTTPError as e:
        logger.error(f"HTTP error: {e}")
        return GenerationResult(
            success=False,
            message=f"Failed to fetch URL: {e}",
            database_path=None,
            project_name=name
        )
    except Exception as e:
        logger.error(f"Error during generation: {e}", exc_info=True)
        return GenerationResult(
            success=False,
            message=f"Error: {str(e)}",
            database_path=None,
            project_name=name
        )


@click.group()
@click.version_option(version='0.1.0')
def main():
    """
    Jedi-MCP: Convert technical documentation websites into MCP servers.
    
    Use 'jedi-mcp generate' to create an MCP server from documentation,
    and 'jedi-mcp serve' to run the server.
    """
    pass


@main.command()
@click.option(
    '--url',
    required=True,
    help='Root documentation URL to process (must be http:// or https://)'
)
@click.option(
    '--name',
    required=True,
    help='Project name for the generated MCP server (alphanumeric, hyphens, underscores only)'
)
@click.option(
    '--rate-limit',
    type=float,
    default=0.5,
    help='Delay between requests in seconds (default: 0.5)'
)
@click.option(
    '--max-retries',
    type=int,
    default=3,
    help='Maximum number of retries for failed requests (default: 3)'
)
@click.option(
    '--timeout',
    type=int,
    default=30,
    help='Request timeout in seconds (default: 30)'
)
@click.option(
    '--db-path',
    type=click.Path(path_type=Path),
    default=None,
    help='Custom database path (default: ~/.jedi-mcp/jedi-mcp.db)'
)
def generate(url: str, name: str, rate_limit: float, max_retries: int, timeout: int, db_path: Path):
    """
    Generate an MCP server from a documentation URL.
    
    This command crawls the documentation website, extracts content,
    groups related pages, and stores everything in a database that
    can be served as an MCP server.
    
    Example:
        jedi-mcp generate --url https://docs.example.com --name example-docs
    """
    # Validate URL
    if not validate_url(url):
        click.echo("❌ Error: Invalid URL format. URL must start with http:// or https://", err=True)
        sys.exit(1)
    
    # Validate project name
    if not validate_project_name(name):
        click.echo(
            "❌ Error: Invalid project name. Name must contain only alphanumeric characters, "
            "hyphens, and underscores.",
            err=True
        )
        sys.exit(1)
    
    # Set default database path if not provided
    if db_path is None:
        db_path = Path.home() / ".jedi-mcp" / "jedi-mcp.db"
    
    # Create crawl configuration
    config = CrawlConfig(
        rate_limit_delay=rate_limit,
        max_retries=max_retries,
        timeout=timeout
    )
    
    click.echo(f"🚀 Starting MCP server generation for '{name}'")
    click.echo(f"📍 URL: {url}")
    click.echo(f"💾 Database: {db_path}")
    click.echo()
    
    # Run async generation
    result = asyncio.run(generate_mcp_server_async(url, name, config, db_path))
    
    # Display result
    if result.success:
        click.echo()
        click.echo("=" * 60)
        click.echo(f"✅ {result.message}")
        click.echo(f"📁 Database location: {result.database_path}")
        click.echo()
        click.echo("To start the MCP server, run:")
        click.echo(f"  jedi-mcp serve --project {result.project_name}")
        click.echo("=" * 60)
    else:
        click.echo()
        click.echo(f"❌ Generation failed: {result.message}", err=True)
        sys.exit(1)


@main.command()
@click.option(
    '--project',
    required=True,
    help='Name of the documentation project to serve'
)
@click.option(
    '--db-path',
    type=click.Path(path_type=Path),
    default=None,
    help='Custom database path (default: ~/.jedi-mcp/jedi-mcp.db)'
)
def serve(project: str, db_path: Path):
    """
    Run the MCP server for a documentation project.
    
    This command starts an MCP server that exposes the documentation
    content as tools that AI coding assistants can use.
    
    Example:
        jedi-mcp serve --project example-docs
    """
    # Set default database path if not provided
    if db_path is None:
        db_path = Path.home() / ".jedi-mcp" / "jedi-mcp.db"
    
    # Check if database exists
    if not db_path.exists():
        click.echo(
            f"❌ Error: Database not found at {db_path}",
            err=True
        )
        click.echo("\nPlease generate a project first using 'jedi-mcp generate'.", err=True)
        sys.exit(1)
    
    # Validate project exists
    db_manager = DatabaseManager(db_path)
    
    try:
        content_groups = db_manager.get_all_content_groups(project)
        
        if not content_groups:
            click.echo(
                f"❌ Error: Project '{project}' not found in database at {db_path}",
                err=True
            )
            click.echo("\nPlease generate the project first using 'jedi-mcp generate'.", err=True)
            sys.exit(1)
        
        click.echo(f"🚀 Starting MCP server for project '{project}'")
        click.echo(f"📁 Database: {db_path}")
        click.echo(f"🔧 Loaded {len(content_groups)} content groups")
        click.echo()
        click.echo("Server is running. Press Ctrl+C to stop.")
        click.echo()
        
        # Set up signal handlers for graceful shutdown
        def signal_handler(sig, frame):
            click.echo("\n\n🛑 Shutting down MCP server...")
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Run the MCP server
        run_mcp_server(project, db_path)
        
    except Exception as e:
        logger.error(f"Failed to start MCP server: {e}", exc_info=True)
        click.echo(f"❌ Error: Failed to start MCP server: {str(e)}", err=True)
        click.echo("\nPlease ensure the project was generated successfully using 'jedi-mcp generate'.", err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
