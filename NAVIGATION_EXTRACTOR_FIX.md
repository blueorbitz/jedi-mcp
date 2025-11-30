# Navigation Extractor Enhancement - Browser-Based Smart Extraction

## Problem
When querying `https://sequelize.org/docs/v6/`, the navigation extractor was only picking up header/version selector links instead of the actual sidebar documentation menu items.

## Root Cause
1. The original approach relied solely on AI to parse HTML, which was inconsistent
2. JavaScript-rendered content wasn't being captured
3. No specific logic for common documentation frameworks (like Docusaurus)

## Solution Implemented

### Approach: Smart DOM Parsing with Headless Browser

Instead of relying on AI, we now use:
1. **Headless browser (Playwright)** - Renders JavaScript and captures the full DOM
2. **Smart DOM parsing** - Detects common documentation patterns (Docusaurus, generic sidebars)
3. **AI fallback** - Only used when smart parsing fails

### Key Features

#### 1. Browser-Based Rendering
- Uses Playwright to render JavaScript-heavy documentation sites
- Waits for dynamic content to load
- Captures the fully rendered DOM

#### 2. Smart Pattern Detection
- **Docusaurus Detection**: Recognizes Docusaurus-specific class names and structure
- **Generic Sidebar Detection**: Handles standard sidebar patterns
- **Hierarchical Extraction**: Properly extracts nested categories and links

#### 3. Accurate Categorization
- Extracts category names from parent elements
- Maintains hierarchical structure (category → links)
- Handles both flat and nested navigation

## Test Results

### Sequelize v6 Documentation
✅ **37 links extracted** with perfect categorization:

- **Core Concepts** (9 links): Model Basics, Model Instances, Model Querying, etc.
- **Advanced Association Concepts** (5 links): Eager Loading, Creating with Associations, etc.
- **Other topics** (21 links): Hooks, Migrations, Transactions, TypeScript, etc.
- **Uncategorized** (2 links): Introduction, Getting Started

✅ **All expected items found** (12/12)
✅ **No false positives** (header/footer links filtered out)
✅ **Fast execution** (~3-4 seconds including browser startup)

## Files Created/Modified

### New Files
- `src/jedi_mcp/smart_navigation_extractor.py` - Smart extraction with browser support
- `src/jedi_mcp/browser_navigation_extractor.py` - Browser-based extraction with AI fallback
- `test_browser_nav.py` - Test script for browser-based extraction
- `test_smart_nav.py` - Test script for smart extraction
- `test_browser_render.py` - Test script to inspect rendered HTML

### Modified Files
- `src/jedi_mcp/navigation_extractor.py` - Enhanced with smart parsing and browser support
- `pyproject.toml` - Added playwright dependency

## Usage

### Basic Usage (Smart Parsing)
```python
from jedi_mcp.navigation_extractor import extract_navigation_links

# Works with pre-fetched HTML
links = extract_navigation_links(html_content, base_url)
```

### Browser Mode (Recommended for JS-heavy sites)
```python
from jedi_mcp.navigation_extractor import extract_navigation_links

# Use browser to render JavaScript
links = extract_navigation_links("", base_url, use_browser=True)
```

### Direct Smart Extraction
```python
from jedi_mcp.smart_navigation_extractor import extract_navigation_smart

# Async function with browser rendering
links = await extract_navigation_smart(url)
```

## Installation

```bash
# Install dependencies
uv pip install playwright

# Install browser binaries
playwright install chromium
```

## Benefits

1. **No AI Required** - Faster, more reliable, no API costs for most sites
2. **JavaScript Support** - Handles modern documentation frameworks
3. **Better Accuracy** - Understands common documentation patterns
4. **Proper Categorization** - Maintains hierarchical structure
5. **Fallback Support** - AI extraction still available for edge cases
