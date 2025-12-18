"""Content processing and grouping using AI to organize documentation."""

import json
import logging
from typing import List
from strands import Agent

from .models import PageContent, ContentGroup
from .model_config import create_content_processing_model

logger = logging.getLogger(__name__)


def process_content(pages: List[PageContent]) -> List[ContentGroup]:
    """
    Group related pages and generate detailed summaries.
    
    Uses Strands SDK Agent to analyze content relationships between pages,
    group them by topic/category, and generate detailed markdown summaries
    for each group.
    
    Args:
        pages: List of crawled page content
        
    Returns:
        List of ContentGroup objects with summaries
        
    Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 9.4
    """
    if not pages:
        logger.warning("No pages provided for content processing")
        return []
    
    logger.info(f"Processing {len(pages)} pages for content grouping")
    
    # Create model for content processing
    model = create_content_processing_model()
    
    # Create AI agent for content analysis
    agent = Agent(
        model=model,
        system_prompt="""You are a technical documentation analyzer. Your task is to:
1. Analyze relationships between documentation pages
2. Group related pages by topic, API category, or conceptual similarity
3. Create logical, coherent groupings that make sense for developers
4. Prioritize preserving important context (code examples, explanations) over strict group limits

Return a JSON array of groups with this structure:
[
  {
    "name": "descriptive-group-name",
    "page_indices": [0, 2, 5],
    "description": "Brief description of what this group covers"
  }
]

Guidelines:
- Group names should be concise, lowercase with hyphens (e.g., "getting-started", "api-reference")
- Each page should belong to exactly one group
- Prioritize preserving important context over strict group count limits (5-15 is a recommendation)
- Group related concepts together (e.g., all authentication pages, all API endpoints)
- Keep code examples and explanations together in the same group
- Consider the logical flow developers would follow"""
    )
    
    # Prepare page summaries for analysis
    page_summaries = []
    for i, page in enumerate(pages):
        # Create a more comprehensive summary of each page to preserve context
        content_preview = page.content[:1000] if len(page.content) > 1000 else page.content
        has_code = len(page.code_blocks) > 0
        # Prioritize code blocks by language for preview
        prioritized_code_preview = _prioritize_code_blocks(page.code_blocks[:3]) if page.code_blocks else []
        
        page_summaries.append({
            "index": i,
            "url": page.url,
            "title": page.title,
            "content_preview": content_preview,
            "has_code_examples": has_code,
            "code_samples": prioritized_code_preview
        })
    
    # Use agent to group pages
    grouping_prompt = f"""Analyze these {len(pages)} documentation pages and group them logically.

Pages:
{json.dumps(page_summaries, indent=2)}

Return only the JSON array of groups."""
    
    logger.info("Requesting content grouping from AI agent")
    grouping_response = agent(grouping_prompt)
    
    # Parse grouping response
    try:
        response_text = str(grouping_response)
        start_idx = response_text.find('[')
        end_idx = response_text.rfind(']') + 1
        if start_idx >= 0 and end_idx > start_idx:
            json_str = response_text[start_idx:end_idx]
            groups_data = json.loads(json_str)
        else:
            logger.warning("No JSON array found in grouping response, using fallback")
            groups_data = _fallback_grouping(pages)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Failed to parse grouping response: {e}, using fallback")
        groups_data = _fallback_grouping(pages)
    
    # Generate detailed summaries for each group
    content_groups = []
    
    for group_data in groups_data:
        group_name = group_data.get('name', 'unknown-group')
        page_indices = group_data.get('page_indices', [])
        group_description = group_data.get('description', '')
        
        # Get pages for this group
        group_pages = [pages[i] for i in page_indices if 0 <= i < len(pages)]
        
        if not group_pages:
            logger.warning(f"Group '{group_name}' has no valid pages, skipping")
            continue
        
        logger.info(f"Generating summary for group '{group_name}' with {len(group_pages)} pages")
        
        # Generate detailed markdown summary
        summary_markdown = _generate_group_summary(
            agent=agent,
            group_name=group_name,
            group_description=group_description,
            pages=group_pages
        )
        
        content_group = ContentGroup(
            name=group_name,
            summary_markdown=summary_markdown,
            pages=group_pages
        )
        content_groups.append(content_group)
    
    logger.info(f"Created {len(content_groups)} content groups")
    return content_groups


def _deduplicate_content(pages: List[PageContent]) -> List[PageContent]:
    """
    Remove duplicate content while preserving unique code examples and explanations.
    Prioritizes JavaScript, Python, and PHP code examples.
    
    Args:
        pages: List of pages to deduplicate
        
    Returns:
        List of pages with duplicates removed but unique content preserved
    """
    seen_content = set()
    seen_code_blocks = set()
    deduplicated_pages = []
    
    for page in pages:
        # Check for content similarity (first 500 chars as fingerprint)
        content_fingerprint = page.content[:500].strip()
        
        # Prioritize code blocks by language and check for uniqueness
        prioritized_code_blocks = _prioritize_code_blocks(page.code_blocks)
        unique_code_blocks = [block for block in prioritized_code_blocks if block not in seen_code_blocks]
        
        # Keep page if it has unique content or unique code blocks
        if content_fingerprint not in seen_content or unique_code_blocks:
            # Update the page with prioritized code blocks
            updated_page = PageContent(
                url=page.url,
                title=page.title,
                content=page.content,
                code_blocks=prioritized_code_blocks
            )
            deduplicated_pages.append(updated_page)
            seen_content.add(content_fingerprint)
            seen_code_blocks.update(page.code_blocks)
    
    return deduplicated_pages


def _prioritize_code_blocks(code_blocks: List[str]) -> List[str]:
    """
    Prioritize code blocks by language: JavaScript, Python, PHP, then others.
    
    Args:
        code_blocks: List of code block strings
        
    Returns:
        Reordered list with prioritized languages first
    """
    if not code_blocks:
        return code_blocks
    
    # Language detection keywords and patterns
    js_indicators = ['function', 'const ', 'let ', 'var ', '=>', 'console.log', 'document.', 'window.', 'async ', 'await ', 'import ', 'export ', 'require(', 'module.exports', 'npm ', 'yarn ', 'node ', '.js', '.ts', '.jsx', '.tsx']
    python_indicators = ['def ', 'import ', 'from ', 'class ', 'if __name__', 'print(', 'pip install', 'python ', '.py', 'self.', 'elif ', 'lambda ', 'yield ', 'with ', 'try:', 'except:', 'finally:']
    php_indicators = ['<?php', 'function ', '$', 'echo ', 'print ', 'class ', 'public ', 'private ', 'protected ', 'namespace ', 'use ', 'composer ', '.php', '->']
    
    def get_language_priority(code_block: str) -> int:
        """Return priority score: 1=JavaScript, 2=Python, 3=PHP, 4=Other"""
        code_lower = code_block.lower()
        
        # Count indicators for each language
        js_score = sum(1 for indicator in js_indicators if indicator.lower() in code_lower)
        python_score = sum(1 for indicator in python_indicators if indicator.lower() in code_lower)
        php_score = sum(1 for indicator in php_indicators if indicator.lower() in code_lower)
        
        # Return priority based on highest score
        if js_score > python_score and js_score > php_score:
            return 1  # JavaScript
        elif python_score > php_score:
            return 2  # Python
        elif php_score > 0:
            return 3  # PHP
        else:
            return 4  # Other
    
    # Sort code blocks by priority
    prioritized_blocks = sorted(code_blocks, key=get_language_priority)
    return prioritized_blocks


def _generate_group_summary(
    agent: Agent,
    group_name: str,
    group_description: str,
    pages: List[PageContent]
) -> str:
    """
    Generate a detailed markdown summary for a content group.
    
    Args:
        agent: Strands SDK Agent for generating summaries
        group_name: Name of the content group
        group_description: Brief description of the group
        pages: Pages in this group
        
    Returns:
        Detailed markdown-formatted summary
    """
    # Deduplicate pages while preserving unique content and code examples
    deduplicated_pages = _deduplicate_content(pages)
    
    # Prepare content for summarization - preserve more context
    pages_content = []
    for page in deduplicated_pages:
        # Prioritize code blocks by language (JavaScript, Python, PHP, others)
        prioritized_code_blocks = _prioritize_code_blocks(page.code_blocks[:10])
        
        # Increase content limit and preserve more code blocks for better context
        page_info = {
            "title": page.title,
            "url": page.url,
            "content": page.content[:3000],  # Increased limit to preserve more context
            "code_blocks": prioritized_code_blocks  # Include prioritized code blocks
        }
        pages_content.append(page_info)
    
    # Create summarization prompt
    summary_prompt = f"""Create a comprehensive markdown summary for this documentation group.

Group: {group_name}
Description: {group_description}

Pages in this group:
{json.dumps(pages_content, indent=2)}

Generate a detailed markdown summary that:
1. Starts with a clear heading (# {group_name.replace('-', ' ').title()})
2. Provides an overview of what this group covers
3. Includes key concepts and important information
4. PRIORITIZES preserving code examples and explanations - these are critical context
5. Includes ALL relevant code examples with proper markdown code blocks
6. PRIORITIZES code examples in this order: JavaScript first, then Python, then PHP, then other languages
7. When multiple code examples exist for the same concept, show JavaScript examples first, followed by Python, then PHP
8. Includes API signatures, function definitions, or important syntax
9. Avoids duplicating identical content across different sections
10. Uses proper markdown formatting:
    - Headings (##, ###) for sections
    - Code blocks with language tags (```javascript, ```python, ```php, etc.)
    - Lists for enumerating features or steps
    - Bold/italic for emphasis where appropriate
11. Provides sufficient context for AI coding assistants to help developers
12. Consolidates similar concepts to avoid redundancy while preserving unique examples

IMPORTANT: Code examples and their explanations are more valuable than brevity. 
Keep all unique code examples and their context. Only remove truly duplicate content.
When presenting code examples, prioritize JavaScript, then Python, then PHP over other languages.
The summary should be detailed enough that a developer can understand the topic without visiting the original pages.
Focus on practical, actionable information.

Return ONLY the markdown content, no additional commentary."""
    
    summary_response = agent(summary_prompt)
    summary_markdown = str(summary_response).strip()
    
    # Ensure the summary has proper markdown structure
    if not summary_markdown.startswith('#'):
        summary_markdown = f"# {group_name.replace('-', ' ').title()}\n\n{summary_markdown}"
    
    return summary_markdown


def _fallback_grouping(pages: List[PageContent]) -> List[dict]:
    """
    Fallback grouping method when AI grouping fails.
    
    Creates simple groups based on URL patterns or alphabetically.
    
    Args:
        pages: List of page content
        
    Returns:
        List of group dictionaries
    """
    from urllib.parse import urlparse
    from collections import defaultdict
    
    # Try to group by URL path segments
    path_groups = defaultdict(list)
    
    for i, page in enumerate(pages):
        parsed = urlparse(page.url)
        path_parts = [p for p in parsed.path.split('/') if p]
        
        # Use first path segment as group, or 'general' if none
        group_key = path_parts[0] if path_parts else 'general'
        path_groups[group_key].append(i)
    
    # Convert to expected format
    groups = []
    for group_name, indices in path_groups.items():
        groups.append({
            "name": group_name,
            "page_indices": indices,
            "description": f"Documentation pages under /{group_name}"
        })
    
    # If we have too many groups (more than 10), consolidate
    if len(groups) > 10:
        # Put everything in one group
        groups = [{
            "name": "documentation",
            "page_indices": list(range(len(pages))),
            "description": "All documentation pages"
        }]
    
    return groups
