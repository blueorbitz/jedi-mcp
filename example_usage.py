"""Example usage of the navigation extractor with Gemini."""

import os
from src.jedi_mcp.navigation_extractor import extract_navigation_links

# Example HTML from a documentation site
example_html = """
<!DOCTYPE html>
<html>
<head>
    <title>Example Documentation</title>
</head>
<body>
    <nav class="sidebar">
        <h2>Getting Started</h2>
        <ul>
            <li><a href="/docs/intro">Introduction</a></li>
            <li><a href="/docs/installation">Installation</a></li>
            <li><a href="/docs/quickstart">Quick Start</a></li>
        </ul>
        
        <h2>API Reference</h2>
        <ul>
            <li><a href="/docs/api/authentication">Authentication</a></li>
            <li><a href="/docs/api/endpoints">Endpoints</a></li>
        </ul>
        
        <h2>External Links</h2>
        <ul>
            <li><a href="https://github.com/example/repo">GitHub</a></li>
            <li><a href="https://twitter.com/example">Twitter</a></li>
        </ul>
    </nav>
    
    <main>
        <h1>Welcome to Example Docs</h1>
        <p>This is the main content area.</p>
    </main>
</body>
</html>
"""

def main():
    """Run the example."""
    # Check if API key is set
    if not os.environ.get("GOOGLE_API_KEY"):
        print("⚠️  Warning: GOOGLE_API_KEY environment variable not set!")
        print("Please set it with: export GOOGLE_API_KEY='your-api-key'")
        print("\nFor testing purposes, the function will use mocked responses.")
        return
    
    print("🔍 Extracting navigation links from example HTML...")
    print(f"📍 Base URL: https://example.com")
    print()
    
    try:
        # Extract links
        links = extract_navigation_links(example_html, "https://example.com")
        
        print(f"✅ Found {len(links)} documentation links:")
        print()
        
        for i, link in enumerate(links, 1):
            print(f"{i}. {link.title or 'Untitled'}")
            print(f"   URL: {link.url}")
            if link.category:
                print(f"   Category: {link.category}")
            print()
        
        # Show what was filtered out
        print("🚫 Filtered out:")
        print("   - External links (GitHub, Twitter)")
        print("   - Non-documentation links")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nMake sure:")
        print("1. GOOGLE_API_KEY is set correctly")
        print("2. You have internet connection")
        print("3. Gemini dependencies are installed: uv pip install 'strands-agents[gemini]'")

if __name__ == "__main__":
    main()
