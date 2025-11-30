"""Test browser-based navigation extraction for Sequelize documentation."""

import asyncio
from src.jedi_mcp.browser_navigation_extractor import extract_navigation_with_browser


async def test_sequelize_with_browser():
    """Test extracting navigation from Sequelize v6 docs using headless browser."""
    url = "https://sequelize.org/docs/v6/"
    
    print(f"🌐 Fetching Sequelize v6 documentation with headless browser: {url}")
    print("   (This will render JavaScript and wait for dynamic content)")
    print()
    
    # Extract navigation links using browser
    print("🤖 Extracting navigation links using browser + AI...")
    links = await extract_navigation_with_browser(url)
    
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
    for category, cat_links in sorted(categories.items()):
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
        "Associations",
        "Eager Loading",
        "Creating with Associations",
        "Hooks",
        "Migrations",
        "Transactions"
    ]
    
    found_titles = [link.title for link in links]
    missing = [item for item in expected_items if item not in found_titles]
    found = [item for item in expected_items if item in found_titles]
    
    print(f"\n✅ Found {len(found)}/{len(expected_items)} expected sidebar items")
    if found:
        print(f"   Found: {', '.join(found[:5])}{'...' if len(found) > 5 else ''}")
    
    if missing:
        print(f"\n⚠️  Missing: {', '.join(missing)}")
    
    return links


if __name__ == "__main__":
    asyncio.run(test_sequelize_with_browser())
