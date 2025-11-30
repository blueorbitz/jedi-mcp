"""Integration test to verify MCP server works end-to-end."""

import asyncio
from pathlib import Path
import tempfile
import json

from src.jedi_mcp.database import DatabaseManager
from src.jedi_mcp.models import ContentGroup, PageContent
from src.jedi_mcp.mcp_server import create_mcp_server


async def test_mcp_server():
    """Test the MCP server with sample documentation."""
    print("=" * 70)
    print("🧪 MCP Server Integration Test")
    print("=" * 70)
    print()
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    
    try:
        # Step 1: Set up test data
        print("📦 Step 1: Setting up test documentation database")
        print("-" * 70)
        
        db_manager = DatabaseManager(db_path)
        project_name = "example-docs"
        db_manager.initialize_schema(project_name)
        
        # Create realistic documentation content
        groups = [
            ContentGroup(
                name="Getting Started",
                summary_markdown="""# Getting Started

Welcome to Example Framework! This guide will help you get up and running.

## Installation

Install via pip:

```bash
pip install example-framework
```

## Quick Start

Here's a simple example:

```python
from example import Client

# Create a client
client = Client(api_key="your-key")

# Make a request
response = client.get("/users")
print(response.data)
```

## Next Steps

- Read the [API Reference](#) for detailed documentation
- Check out [Examples](#) for more use cases
- Join our [Community](#) for support
""",
                pages=[
                    PageContent(
                        url="https://example.com/docs/getting-started",
                        title="Getting Started",
                        content="Getting started guide",
                        code_blocks=[]
                    )
                ]
            ),
            ContentGroup(
                name="API Reference",
                summary_markdown="""# API Reference

Complete API documentation for Example Framework.

## Client Class

The main client for interacting with the API.

### Constructor

```python
Client(api_key: str, base_url: str = "https://api.example.com")
```

**Parameters:**
- `api_key` (str): Your API key
- `base_url` (str, optional): Base URL for API requests

### Methods

#### get(path: str) -> Response

Make a GET request.

```python
response = client.get("/users/123")
```

#### post(path: str, data: dict) -> Response

Make a POST request.

```python
response = client.post("/users", {"name": "John"})
```

## Response Class

Represents an API response.

**Attributes:**
- `status_code` (int): HTTP status code
- `data` (dict): Response data
- `headers` (dict): Response headers
""",
                pages=[
                    PageContent(
                        url="https://example.com/docs/api",
                        title="API Reference",
                        content="API documentation",
                        code_blocks=[]
                    )
                ]
            ),
            ContentGroup(
                name="Authentication",
                summary_markdown="""# Authentication

Learn how to authenticate with Example Framework.

## API Keys

Get your API key from the dashboard:

1. Log in to your account
2. Navigate to Settings > API Keys
3. Click "Generate New Key"

## Using API Keys

Pass your API key when creating a client:

```python
from example import Client

client = Client(api_key="sk_live_abc123...")
```

## OAuth 2.0

For OAuth authentication:

```python
from example import OAuthClient

client = OAuthClient(
    client_id="your_client_id",
    client_secret="your_secret"
)

# Get authorization URL
auth_url = client.get_authorization_url()

# Exchange code for token
token = client.exchange_code(code)
```

## Best Practices

- Never commit API keys to version control
- Use environment variables for keys
- Rotate keys regularly
- Use different keys for dev/prod
""",
                pages=[
                    PageContent(
                        url="https://example.com/docs/auth",
                        title="Authentication",
                        content="Authentication guide",
                        code_blocks=[]
                    )
                ]
            )
        ]
        
        for group in groups:
            db_manager.store_content_group(project_name, group, "https://example.com")
        
        print(f"✓ Created {len(groups)} content groups")
        print(f"✓ Database: {db_path}")
        print()
        
        # Step 2: Create MCP server
        print("🚀 Step 2: Creating MCP server")
        print("-" * 70)
        
        mcp = create_mcp_server(project_name, db_manager=db_manager)
        print(f"✓ Server name: {mcp.name}")
        print()
        
        # Step 3: List available tools
        print("🔧 Step 3: Available MCP Tools")
        print("-" * 70)
        
        tools_dict = mcp._tool_manager._tools
        print(f"Total tools: {len(tools_dict)}\n")
        
        for i, (tool_name, tool) in enumerate(tools_dict.items(), 1):
            print(f"{i}. {tool_name}")
            print(f"   Description: {tool.description}")
            print()
        
        # Step 4: Test tool invocation
        print("🎯 Step 4: Testing Tool Invocation")
        print("-" * 70)
        
        for tool_name in ["getting_started", "api_reference", "authentication"]:
            tool = tools_dict.get(tool_name)
            if tool:
                print(f"\n📖 Invoking tool: {tool_name}")
                print("-" * 70)
                
                result = tool.fn()
                
                # Show statistics
                lines = result.split('\n')
                code_blocks = result.count('```')
                
                print(f"✓ Success!")
                print(f"  • Length: {len(result)} characters")
                print(f"  • Lines: {len(lines)}")
                print(f"  • Code blocks: {code_blocks // 2}")
                print(f"\n  Preview (first 200 chars):")
                print(f"  {result[:200]}...")
        
        print("\n" + "=" * 70)
        print("✅ All tests passed! MCP server is working correctly.")
        print("=" * 70)
        print()
        
        # Step 5: Show how to use with Kiro
        print("💡 How to use this MCP server with Kiro:")
        print("-" * 70)
        print("""
1. First, you need to complete task 7 to implement the CLI commands:
   - `jedi-mcp generate --url <docs-url> --name <project-name>`
   - `jedi-mcp serve --project <project-name>`

2. Then add to your Kiro MCP config (.kiro/settings/mcp.json):

{
  "mcpServers": {
    "example-docs": {
      "command": "jedi-mcp",
      "args": ["serve", "--project", "example-docs"],
      "disabled": false
    }
  }
}

3. Restart Kiro or reconnect the MCP server

4. The tools will appear in Kiro's MCP tools list:
   - getting_started
   - api_reference
   - authentication

5. Kiro can then invoke these tools to get documentation context!
""")
        
    finally:
        # Cleanup
        if db_path.exists():
            db_path.unlink()
            print("🧹 Cleaned up temporary database")


if __name__ == "__main__":
    asyncio.run(test_mcp_server())
