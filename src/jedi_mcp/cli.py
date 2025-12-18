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
from bs4 import BeautifulSoup

from .models import CrawlConfig, GenerationResult
from .database import DatabaseManager
from .navigation_extractor import extract_navigation_links, extract_navigation_links_async
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


def _display_links_table(links: list, start_idx: int = 0, count: int = 20):
    """Display links in a formatted table."""
    click.echo()
    click.echo("=" * 120)
    click.echo(f"{'Index':<8} {'Title':<40} {'Category':<25} {'URL':<47}")
    click.echo("=" * 120)
    
    end_idx = min(start_idx + count, len(links))
    for i in range(start_idx, end_idx):
        link = links[i]
        index = f"[{i+1}]"
        title = (link.title or "No title")[:38]
        category = (link.category or "Uncategorized")[:23]
        url = link.url[:45]
        
        click.echo(f"{index:<8} {title:<40} {category:<25} {url:<47}")
    
    click.echo("=" * 120)
    click.echo(f"Showing {start_idx+1}-{end_idx} of {len(links)} total links")
    click.echo()


async def _verify_and_filter_links(links: list, html_content: str, base_url: str, config: CrawlConfig) -> list:
    """
    Interactive verification and filtering of extracted links.
    
    Allows user to:
    - View links in a table format
    - Remove specific links by index
    - Search for additional elements
    - Proceed with scraping
    """
    current_links = links.copy()
    page = 0
    page_size = 20
    
    while True:
        # Display current page of links
        _display_links_table(current_links, page * page_size, page_size)
        
        click.echo("Options:")
        click.echo("  [p] Proceed with scraping these links")
        click.echo("  [n] Next page")
        click.echo("  [b] Previous page")
        click.echo("  [r] Remove links by index (e.g., '1,3,5-10')")
        click.echo("  [s] Search for additional elements (CSS selector)")
        click.echo("  [a] Show all links (no pagination)")
        click.echo("  [c] Cancel generation")
        click.echo()
        
        choice = click.prompt("Your choice", type=str, default="p").lower().strip()
        
        if choice == "p":
            # Proceed with scraping
            if click.confirm(f"\nProceed with scraping {len(current_links)} links?", default=True):
                return current_links
        
        elif choice == "n":
            # Next page
            if (page + 1) * page_size < len(current_links):
                page += 1
            else:
                click.echo("⚠️  Already on last page")
        
        elif choice == "b":
            # Previous page
            if page > 0:
                page -= 1
            else:
                click.echo("⚠️  Already on first page")
        
        elif choice == "r":
            # Remove links by index
            click.echo()
            indices_str = click.prompt("Enter indices to remove (e.g., '1,3,5-10' or 'all')", type=str)
            
            if indices_str.lower() == "all":
                if click.confirm("Remove ALL links? This will cancel the generation.", default=False):
                    return []
                continue
            
            try:
                indices_to_remove = set()
                for part in indices_str.split(','):
                    part = part.strip()
                    if '-' in part:
                        # Range
                        start, end = part.split('-')
                        indices_to_remove.update(range(int(start) - 1, int(end)))
                    else:
                        # Single index
                        indices_to_remove.add(int(part) - 1)
                
                # Filter out invalid indices
                valid_indices = {i for i in indices_to_remove if 0 <= i < len(current_links)}
                
                if valid_indices:
                    # Remove links
                    current_links = [link for i, link in enumerate(current_links) if i not in valid_indices]
                    click.echo(f"✓ Removed {len(valid_indices)} link(s). {len(current_links)} remaining.")
                    # Reset to first page
                    page = 0
                else:
                    click.echo("⚠️  No valid indices provided")
            
            except ValueError:
                click.echo("❌ Invalid format. Use comma-separated numbers or ranges (e.g., '1,3,5-10')")
        
        elif choice == "s":
            # Search for additional elements
            click.echo()
            click.echo("Enter a CSS selector to find additional links (e.g., 'nav.sidebar a', '.docs-menu a')")
            selector = click.prompt("CSS selector", type=str)
            
            try:
                soup = BeautifulSoup(html_content, 'lxml')
                elements = soup.select(selector)
                
                if not elements:
                    click.echo(f"⚠️  No elements found matching selector: {selector}")
                    continue
                
                click.echo(f"✓ Found {len(elements)} elements")
                
                # Extract links from elements
                from .navigation_extractor import _create_doc_link
                from urllib.parse import urlparse
                
                base_domain = urlparse(base_url).netloc
                new_links = []
                
                for elem in elements:
                    if elem.name == 'a' and elem.get('href'):
                        doc_link = _create_doc_link(elem, base_url, base_domain, None)
                        if doc_link:
                            new_links.append(doc_link)
                    else:
                        # Look for links inside the element
                        for a_tag in elem.find_all('a', href=True):
                            doc_link = _create_doc_link(a_tag, base_url, base_domain, None)
                            if doc_link:
                                new_links.append(doc_link)
                
                if new_links:
                    # Remove duplicates
                    existing_urls = {link.url for link in current_links}
                    unique_new_links = [link for link in new_links if link.url not in existing_urls]
                    
                    if unique_new_links:
                        current_links.extend(unique_new_links)
                        click.echo(f"✓ Added {len(unique_new_links)} new link(s). Total: {len(current_links)}")
                    else:
                        click.echo("⚠️  All found links were already in the list")
                else:
                    click.echo("⚠️  No valid documentation links found in selected elements")
            
            except Exception as e:
                click.echo(f"❌ Error searching for elements: {e}")
        
        elif choice == "a":
            # Show all links
            _display_links_table(current_links, 0, len(current_links))
            click.echo("Press Enter to continue...")
            click.getchar()
        
        elif choice == "c":
            # Cancel
            if click.confirm("Cancel generation?", default=False):
                return []
        
        else:
            click.echo("⚠️  Invalid choice. Please try again.")


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
        
        # First, try fast HTML-based extraction
        async with httpx.AsyncClient(timeout=config.timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            html_content = response.text
        
        click.echo(f"   Trying fast HTML-based extraction...")
        links = extract_navigation_links(html_content, url, use_browser=False)
        
        # If no links found, offer browser-based extraction
        if not links:
            click.echo(f"⚠️  No navigation links found with fast extraction.")
            click.echo(f"   This might be a site with JavaScript-rendered navigation (e.g., Microsoft Learn, React-based docs).")
            
            if click.confirm(f"🌐 Would you like to try browser-based extraction? (slower but handles JavaScript)"):
                click.echo(f"   Using browser-based extraction...")
                try:
                    links = await extract_navigation_links_async(url)
                    if links:
                        click.echo(f"✓ Browser-based extraction found {len(links)} links!")
                    else:
                        click.echo(f"⚠️  Browser-based extraction also found no links.")
                except Exception as e:
                    click.echo(f"❌ Browser-based extraction failed: {e}")
                    click.echo(f"   Make sure Playwright is installed: pip install playwright && playwright install")
            else:
                click.echo(f"   Skipping browser-based extraction.")
        
        if not links:
            return GenerationResult(
                success=False,
                message="No documentation links found. Please check the URL.",
                database_path=None,
                project_name=name
            )
        
        click.echo(f"✓ Found {len(links)} documentation links")
        click.echo()
        
        # Interactive verification loop
        links = await _verify_and_filter_links(links, html_content, url, config)
        
        if not links:
            return GenerationResult(
                success=False,
                message="No links to scrape after filtering.",
                database_path=None,
                project_name=name
            )
        
        click.echo()
        
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
    'jedi-mcp list-projects' to see available projects,
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
    '--db-path',
    type=click.Path(path_type=Path),
    default=None,
    help='Custom database path (default: ~/.jedi-mcp/jedi-mcp.db)'
)
def list_projects(db_path: Path):
    """
    List all documentation projects in the database.
    
    This command displays all projects that have been generated
    and are available to serve.
    
    Example:
        jedi-mcp list-projects
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
        click.echo("\nNo projects have been generated yet. Use 'jedi-mcp generate' to create one.", err=True)
        sys.exit(1)
    
    # Get all projects
    db_manager = DatabaseManager(db_path)
    
    try:
        projects = db_manager.get_all_projects()
        
        if not projects:
            click.echo("📭 No projects found in the database.")
            click.echo("\nUse 'jedi-mcp generate' to create a new project.")
            return
        
        click.echo(f"📚 Found {len(projects)} project(s) in database:")
        click.echo(f"📁 Database: {db_path}")
        click.echo()
        
        for project in projects:
            click.echo(f"  • {project['name']}")
            click.echo(f"    URL: {project['root_url']}")
            click.echo(f"    Groups: {project['content_groups_count']}")
            click.echo(f"    Created: {project['created_at']}")
            click.echo()
        
        click.echo("To serve a project, run:")
        click.echo(f"  jedi-mcp serve --project <project-name>")
        
    except Exception as e:
        logger.error(f"Failed to list projects: {e}", exc_info=True)
        click.echo(f"❌ Error: Failed to list projects: {str(e)}", err=True)
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
@click.option(
    '--transport',
    type=click.Choice(['stdio', 'sse'], case_sensitive=False),
    default='stdio',
    help='Transport type: stdio (default) or sse for HTTP/SSE'
)
@click.option(
    '--host',
    default='localhost',
    help='Host to bind to for SSE transport (default: localhost)'
)
@click.option(
    '--port',
    type=int,
    default=8000,
    help='Port to bind to for SSE transport (default: 8000)'
)
def serve(project: str, db_path: Path, transport: str, host: str, port: int):
    """
    Run the MCP server for a documentation project.
    
    This command starts an MCP server that exposes the documentation
    content as tools that AI coding assistants can use.
    
    Examples:
        jedi-mcp serve --project example-docs
        jedi-mcp serve --project example-docs --transport sse --port 8000
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
        click.echo(f"🚦 Transport: {transport}")
        
        if transport == 'sse':
            click.echo(f"🌐 Server URL: http://{host}:{port}")
            click.echo()
            click.echo("Connect to this server using:")
            click.echo(f"  - MCP Inspector: npx @modelcontextprotocol/inspector")
            click.echo(f"  - Then connect to: http://{host}:{port}/sse")
        
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
        run_mcp_server(project, db_path, transport=transport, host=host, port=port)
        
    except Exception as e:
        logger.error(f"Failed to start MCP server: {e}", exc_info=True)
        click.echo(f"❌ Error: Failed to start MCP server: {str(e)}", err=True)
        click.echo("\nPlease ensure the project was generated successfully using 'jedi-mcp generate'.", err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
