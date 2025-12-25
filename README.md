# Jedi-MCP

Convert technical documentation websites into Model Context Protocol (MCP) servers.

## Overview

Jedi-MCP is a Python CLI tool that transforms technical documentation websites into MCP servers, enabling AI coding assistants (Kiro, GitHub Copilot, Cursor, Windsurf, etc.) to access detailed framework, library, API, SDK, and language documentation during development.

## Features

- **AI-Powered Navigation Extraction**: Uses Strands SDK to intelligently identify documentation links
- **Smart Content Crawling**: Fetches and extracts main content while filtering out navigation and non-content elements
- **Intelligent Grouping**: Groups related documentation pages using AI
- **Detailed Summaries**: Generates comprehensive markdown summaries with code examples and API signatures
- **MCP Server Generation**: Exposes each content group as an MCP tool for AI coding assistants
- **Multiple Transport Options**: Supports both stdio (for MCP clients) and SSE (for HTTP/Inspector access)

## Installation

### Option 1: Direct Usage with uvx (Recommended)

```bash
# Install UV if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Use directly with uvx from local directory
uvx --from . jedi-mcp generate --url https://docs.example.com --name example-docs
uvx --from . jedi-mcp serve --project example-docs

# Or once published to PyPI (coming soon):
# uvx jedi-mcp generate --url https://docs.example.com --name example-docs
# uvx jedi-mcp serve --project example-docs
```

### Option 2: Local Development Installation

```bash
# Clone the repository
git clone <repository-url>
cd jedi-mcp

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"

# Gemini support is included by default
# For Bedrock support, install with: uv pip install -e ".[bedrock]"
# For all providers: uv pip install -e ".[all]"
```

## Configuration

### Model Provider Selection

Jedi-MCP supports multiple AI providers for navigation extraction and content processing. You can choose between:

- **Google Gemini** (default) - Fast and cost-effective
- **AWS Bedrock** - Enterprise-grade with various model options

#### Using Google Gemini (Default)

1. Get your API key from [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Set the environment variable:

```bash
# On Linux/Mac
export JEDI_MODEL_PROVIDER=gemini
export GOOGLE_API_KEY="your-api-key-here"

# On Windows (PowerShell)
$env:JEDI_MODEL_PROVIDER="gemini"
$env:GOOGLE_API_KEY="your-api-key-here"

# On Windows (CMD)
set JEDI_MODEL_PROVIDER=gemini
set GOOGLE_API_KEY=your-api-key-here
```

Or create a `.env` file in the project root:

```
JEDI_MODEL_PROVIDER=gemini
GOOGLE_API_KEY=your-api-key-here
```

#### Using AWS Bedrock

1. Configure AWS credentials (via environment variables, credentials file, or IAM role)
2. Set the model provider:

```bash
# On Linux/Mac
export JEDI_MODEL_PROVIDER=bedrock
export AWS_REGION=us-east-1

# On Windows (PowerShell)
$env:JEDI_MODEL_PROVIDER="bedrock"
$env:AWS_REGION="us-east-1"
```

Or in `.env`:

```
JEDI_MODEL_PROVIDER=bedrock
AWS_REGION=us-east-1
```

#### Advanced Configuration

You can override specific model IDs for different tasks:

```bash
# Navigation extraction model
export JEDI_NAVIGATION_MODEL=gemini-2.0-flash-exp  # For Gemini
# or
export JEDI_NAVIGATION_MODEL=qwen.qwen3-coder-30b-a3b-v1:0  # For Bedrock

# Content processing model
export JEDI_CONTENT_MODEL=gemini-2.0-flash-exp  # For Gemini
# or
export JEDI_CONTENT_MODEL=qwen.qwen3-coder-30b-a3b-v1:0  # For Bedrock
```

**Default Models:**
- Gemini: `gemini-2.0-flash-exp` for both navigation and content processing
- Bedrock: `us.anthropic.claude-3-5-sonnet-20241022-v2:0` for both tasks

## Usage

### Generate MCP Server from Documentation

```bash
# Using uvx from local directory (recommended)
uvx --from . jedi-mcp generate --url https://docs.example.com --name example-docs

# Or using local installation
jedi-mcp generate --url https://docs.example.com --name example-docs

# Once published to PyPI:
# uvx jedi-mcp generate --url https://docs.example.com --name example-docs
```

### List Available Projects

```bash
# Using uvx from local directory
uvx --from . jedi-mcp list-projects

# Or using local installation
jedi-mcp list-projects

# Once published to PyPI:
# uvx jedi-mcp list-projects
```

This will display all projects in the database with their metadata:
- Project name
- Root URL
- Number of content groups
- Creation timestamp

### Run the MCP Server

**Stdio transport (for MCP clients like Kiro):**
```bash
# Using uvx from local directory (recommended)
uvx --from . jedi-mcp serve --project example-docs

# Or using local installation
jedi-mcp serve --project example-docs

# Once published to PyPI:
# uvx jedi-mcp serve --project example-docs
```

**SSE transport (for HTTP/localhost access and MCP Inspector):**
```bash
# Using uvx from local directory
uvx --from . jedi-mcp serve --project example-docs --transport sse --port 8000

# Or using local installation
jedi-mcp serve --project example-docs --transport sse --port 8000

# Once published to PyPI:
# uvx jedi-mcp serve --project example-docs --transport sse --port 8000
```

The server will be available at `http://localhost:8000/sse`

## Testing with MCP Inspector

The MCP Inspector is a web-based tool for testing and debugging your MCP server. It lets you explore available tools, test them with different inputs, and see the responses.

### Method 1: Direct Connection (Recommended)

Start your server with SSE transport and connect via browser:

```bash
# Terminal 1: Start the MCP server with SSE transport
jedi-mcp serve --project example-docs --transport sse --port 8000

# Terminal 2: Launch MCP Inspector
npx @modelcontextprotocol/inspector
```

Then in the Inspector web interface:
1. Open your browser to `http://localhost:5173` (or the URL shown by the inspector)
2. Click "Connect to Server"
3. Enter the server URL: `http://localhost:8000/sse`
4. Click "Connect"

### Method 2: Inspector Auto-Launch

Let the Inspector launch your server automatically:

```bash
npx @modelcontextprotocol/inspector jedi-mcp serve --project example-docs
```

This will start both the Inspector and your server, connecting them automatically.

### Using the Inspector

Once connected, you can:
- **View Tools**: See all available documentation tools (one per content group)
- **Test Tools**: Click any tool to invoke it and see the markdown documentation
- **Inspect Responses**: View the full markdown content returned by each tool
- **Debug Issues**: Check connection status and error messages

Example workflow:
1. Connect to your server using one of the methods above
2. Browse the list of available tools (e.g., `getting_started`, `api_reference`, etc.)
3. Click a tool name to invoke it
4. Review the returned markdown documentation
5. Test different tools to verify all content groups are accessible

### Configure in Kiro IDE

To use with Kiro, add to `.kiro/settings/mcp.json`:

**Option 1: Direct uvx usage from local directory:**
```json
{
  "mcpServers": {
    "jedi-mcp": {
      "command": "uvx",
      "args": ["--from", "/path/to/jedi-mcp", "jedi-mcp", "serve", "--project", "example-docs"],
      "env": {
        "PYTHONIOENCODING": "utf-8"
      },
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

**Option 1b: Direct uvx usage (once published to PyPI):**
```json
{
  "mcpServers": {
    "jedi-mcp": {
      "command": "uvx",
      "args": ["jedi-mcp", "serve", "--project", "example-docs"],
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

**Option 2: Local installation:**
```json
{
  "mcpServers": {
    "jedi-mcp": {
      "command": "jedi-mcp",
      "args": ["serve", "--project", "example-docs"],
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

**Option 3: HTTP/SSE transport:**
```json
{
  "mcpServers": {
    "jedi-mcp": {
      "url": "http://localhost:8000/sse",
      "transport": "http"
    }
  }
}
```

### Command Options

**Generate command:**
- `--url`: Documentation website URL (required)
- `--name`: Project name (required)
- `--rate-limit`: Delay between requests in seconds (default: 0.5)
- `--max-retries`: Maximum retries for failed requests (default: 3)
- `--timeout`: Request timeout in seconds (default: 30)
- `--db-path`: Custom database path (default: ~/.jedi-mcp/jedi-mcp.db)

**List-projects command:**
- `--db-path`: Custom database path (default: ~/.jedi-mcp/jedi-mcp.db)

**Serve command:**
- `--project`: Project name to serve (required)
- `--transport`: Transport type - `stdio` or `sse` (default: stdio)
- `--host`: Host to bind for SSE transport (default: localhost)
- `--port`: Port for SSE transport (default: 8000)
- `--db-path`: Custom database path (default: ~/.jedi-mcp/jedi-mcp.db)

## Requirements

- Python 3.10 or higher
- UV package manager

## Development

```bash
# Install development dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Run property-based tests
pytest tests/property/
```

## Publishing

To publish to PyPI for easier uvx usage:

```bash
# Build the package
uv build

# Publish to PyPI (requires PyPI account and API token)
uv publish

# Or publish to TestPyPI first
uv publish --repository testpypi
```

Once published, users can use it directly with uvx:

```bash
uvx jedi-mcp generate --url https://docs.example.com --name example-docs
uvx jedi-mcp serve --project example-docs
```

## License

MIT
