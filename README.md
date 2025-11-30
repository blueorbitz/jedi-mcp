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

```bash
jedi-mcp serve --project example-docs
```

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
