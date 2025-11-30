"""Test smart navigation extraction for Sequelize documentation."""

import asyncio
from src.jedi_mcp.smart_navigation_extractor import extract_navigation_smart


async def test_smart_extraction():
    """Test extracting navigation from Sequelize v6 docs using smart extraction."""
    url = "https://sequelize.org/docs/v6/"
    
    print(f"🌐 Fetching Sequelize v6 documentation: {url}")
    print("   Using headless browser + smart DOM parsing (no AI needed)")
    print()
    
    # Extract navigation links
    print("🔍 Extracting navigation links...")
    links = await extract_navigation_smart(url)
    
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
        print(f"   Found: {', '.join(found[:8])}{'...' if len(found) > 8 else ''}")
    
    if missing:
        print(f"\n⚠️  Missing: {', '.join(missing)}")
    else:
        print("\n🎉 All expected items found!")
    
    return links


if __name__ == "__main__":
    asyncio.run(test_smart_extraction())
