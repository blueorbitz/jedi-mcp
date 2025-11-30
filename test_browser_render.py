"""Test browser rendering to see what HTML structure we get."""

import asyncio
from src.jedi_mcp.browser_navigation_extractor import fetch_rendered_html
from bs4 import BeautifulSoup


async def test_browser_render():
    """Fetch and inspect the rendered HTML from Sequelize docs."""
    url = "https://sequelize.org/docs/v6/"
    
    print(f"🌐 Fetching page with headless browser: {url}")
    print()
    
    # Fetch rendered HTML
    html_content = await fetch_rendered_html(url)
    
    print(f"✅ Page fetched successfully")
    print(f"📄 HTML size: {len(html_content)} characters")
    print()
    
    # Parse and analyze structure
    soup = BeautifulSoup(html_content, 'lxml')
    
    # Find navigation elements
    print("🔍 Looking for navigation elements...")
    print()
    
    # Check for sidebar
    sidebar = soup.find(['aside', 'nav'], class_=lambda x: x and any(
        term in str(x).lower() for term in ['sidebar', 'side-nav', 'sidenav', 'docs-nav', 'doc-nav', 'menu']
    ))
    
    if sidebar:
        print(f"✅ Found sidebar element: <{sidebar.name}> with class='{sidebar.get('class')}'")
        
        # Count links in sidebar
        links = sidebar.find_all('a', href=True)
        print(f"   Contains {len(links)} links")
        
        # Show first few links
        print("\n   First 10 links:")
        for i, link in enumerate(links[:10], 1):
            href = link['href']
            text = link.get_text(strip=True)
            print(f"   {i}. {text[:50]} -> {href}")
        
        # Save sidebar HTML to file for inspection
        with open('sidebar_html.html', 'w', encoding='utf-8') as f:
            f.write(str(sidebar))
        print(f"\n💾 Saved sidebar HTML to sidebar_html.html")
        
    else:
        print("❌ No sidebar found with common patterns")
        
        # Try to find any nav elements
        nav_elements = soup.find_all(['nav', 'aside'])
        print(f"\n   Found {len(nav_elements)} nav/aside elements:")
        for i, nav in enumerate(nav_elements, 1):
            classes = nav.get('class', [])
            nav_id = nav.get('id', '')
            link_count = len(nav.find_all('a', href=True))
            print(f"   {i}. <{nav.name}> class={classes} id={nav_id} ({link_count} links)")
    
    # Save full HTML for inspection
    with open('full_page.html', 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"\n💾 Saved full page HTML to full_page.html")


if __name__ == "__main__":
    asyncio.run(test_browser_render())
