"""Test navigation extraction for Sequelize documentation."""

import asyncio
import httpx
from src.jedi_mcp.navigation_extractor import extract_navigation_links


async def test_sequelize_navigation():
    """Test extracting navigation from Sequelize v6 docs."""
    url = "https://sequelize.org/docs/v6/"
    
    print(f"🔍 Fetching Sequelize v6 documentation from: {url}")
    print()
    
    # Fetch the page
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=30.0)
        response.raise_for_status()
        html_content = response.text
    
    print("✅ Page fetched successfully")
    print(f"📄 HTML size: {len(html_content)} characters")
    print()
    
    # Extract navigation links
    print("🤖 Extracting navigation links using AI...")
    links = extract_navigation_links(html_content, url)
    
    print(f"\n✅ Found {len(links)} documentation links")
    print()
    
    # Group by category
    categories = {}
    for link in links:
        category = link.category or "Uncategorized"
        if category not in categories:
            categories[category] = []
        categories[category].append(link)
    
    # Display results
    print("📚 Links by category:")
    print("=" * 80)
    for category, cat_links in categories.items():
        print(f"\n{category} ({len(cat_links)} links):")
        print("-" * 80)
        for link in cat_links:
            print(f"  • {link.title}")
            print(f"    {link.url}")
    
    print("\n" + "=" * 80)
    
    # Check if we got the expected sidebar items
    expected_items = [
        "Model Basics",
        "Model Instances", 
        "Model Querying - Basics",
        "Getters, Setters & Virtuals",
        "Validations & Constraints",
        "Raw Queries",
        "Associations"
    ]
    
    found_titles = [link.title for link in links]
    missing = [item for item in expected_items if item not in found_titles]
    
    if missing:
        print(f"\n⚠️  Missing expected sidebar items: {missing}")
    else:
        print(f"\n✅ All expected sidebar items found!")
    
    return links


if __name__ == "__main__":
    asyncio.run(test_sequelize_navigation())
