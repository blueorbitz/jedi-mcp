"""Test script to verify Gemini API connection."""

import os
from dotenv import load_dotenv
from strands import Agent
from strands.models.gemini import GeminiModel

# Load environment variables from .env file
load_dotenv()


def test_gemini_api():
    """Test if Gemini API key is working."""
    print("🔍 Testing Gemini API Connection...")
    print()
    
    # Check if API key is set
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("❌ GOOGLE_API_KEY environment variable is not set!")
        print("\nPlease set it with:")
        print("  PowerShell: $env:GOOGLE_API_KEY='your-api-key'")
        print("  CMD: set GOOGLE_API_KEY=your-api-key")
        return False
    
    print(f"✅ API Key found: {api_key[:10]}...{api_key[-4:]}")
    print()
    
    try:
        # Create Gemini model
        print("📡 Initializing Gemini model (gemini-2.5-flash)...")
        model = GeminiModel(
            client_args={
                "api_key": api_key,
            },
            model_id="gemini-2.5-flash",
            params={
                "temperature": 0.7,
                "max_output_tokens": 1024,
            }
        )
        print("✅ Model initialized successfully")
        print()
        
        # Create agent
        print("🤖 Creating Strands Agent...")
        agent = Agent(
            model=model,
            system_prompt="You are a helpful assistant."
        )
        print("✅ Agent created successfully")
        print()
        
        # Test with a simple query
        print("💬 Sending test query: 'What is 2+2? Answer with just the number.'")
        response = agent("What is 2+2? Answer with just the number.")
        print(f"✅ Response received: {response}")
        print()
        
        print("=" * 60)
        print("🎉 SUCCESS! Gemini API is working correctly!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print()
        print("=" * 60)
        print("❌ ERROR: Failed to connect to Gemini API")
        print("=" * 60)
        print(f"\nError details: {e}")
        print("\nPossible issues:")
        print("1. Invalid API key")
        print("2. API key doesn't have proper permissions")
        print("3. Network connectivity issues")
        print("4. Gemini API quota exceeded")
        print("\nGet a new API key at: https://aistudio.google.com/app/apikey")
        return False


def test_navigation_extractor():
    """Test the navigation extractor with real Gemini API."""
    print("\n" + "=" * 60)
    print("🧪 Testing Navigation Extractor with Gemini")
    print("=" * 60)
    print()
    
    from src.jedi_mcp.navigation_extractor import extract_navigation_links
    
    # Simple test HTML
    test_html = """
    <html>
        <nav>
            <h2>Documentation</h2>
            <a href="/docs/intro">Introduction</a>
            <a href="/docs/guide">User Guide</a>
            <a href="/api/reference">API Reference</a>
            <a href="https://twitter.com/example">Twitter</a>
        </nav>
    </html>
    """
    
    try:
        print("📄 Extracting links from test HTML...")
        links = extract_navigation_links(test_html, "https://example.com")
        
        print(f"✅ Extracted {len(links)} documentation links:")
        print()
        
        for i, link in enumerate(links, 1):
            print(f"  {i}. {link.title or 'Untitled'}")
            print(f"     URL: {link.url}")
            if link.category:
                print(f"     Category: {link.category}")
            print()
        
        print("=" * 60)
        print("🎉 Navigation Extractor is working with Gemini!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"❌ Error in navigation extractor: {e}")
        return False


if __name__ == "__main__":
    print()
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "GEMINI API CONNECTION TEST" + " " * 21 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    # Test basic Gemini connection
    basic_test_passed = test_gemini_api()
    
    if basic_test_passed:
        # Test navigation extractor
        nav_test_passed = test_navigation_extractor()
        
        if nav_test_passed:
            print("\n✨ All tests passed! Your Gemini integration is ready to use.")
        else:
            print("\n⚠️  Basic API works, but navigation extractor needs attention.")
    else:
        print("\n❌ Please fix the API key issue before proceeding.")
