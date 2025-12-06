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

```bash
# Install UV if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repository
git clone <repository-url>
cd jedi-mcp

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"

# Install Gemini support (required for AI-powered navigation extraction)
uv pip install 'strands-agents[gemini]'
```

## Configuration

### Google Gemini API Key

Jedi-MCP uses Google Gemini for AI-powered navigation extraction. You need to set up your API key:

1. Get your API key from [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Set the environment variable:

```bash
# On Linux/Mac
export GOOGLE_API_KEY="your-api-key-here"

# On Windows (PowerShell)
$env:GOOGLE_API_KEY="your-api-key-here"

# On Windows (CMD)
set GOOGLE_API_KEY=your-api-key-here
```

Alternatively, create a `.env` file in the project root:

```
GOOGLE_API_KEY=your-api-key-here
```

## Usage

### Generate MCP Server from Documentation

```bash
jedi-mcp generate --url https://docs.example.com --name example-docs
```

### Run the MCP Server

**Stdio transport (for MCP clients like Kiro):**
```bash
jedi-mcp serve --project example-docs
```

**SSE transport (for HTTP/localhost access and MCP Inspector):**
```bash
jedi-mcp serve --project example-docs --transport sse --port 8000
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

or


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

## License

MIT
