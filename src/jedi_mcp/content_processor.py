"""Content processing and grouping using AI to organize documentation."""

import os
import json
import logging
from typing import List
from strands import Agent
from strands.models.gemini import GeminiModel
from dotenv import load_dotenv

from .models import PageContent, ContentGroup

# Load environment variables from .env file
load_dotenv()

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
    
    # Configure Gemini model
    gemini_model = GeminiModel(
        client_args={
            "api_key": os.environ.get("GOOGLE_API_KEY"),
        },
        model_id="gemini-2.5-flash",
        params={
            "temperature": 0.3,
            "max_output_tokens": 8192,
            "top_p": 0.9,
        }
    )
    
    # Create AI agent for content analysis
    agent = Agent(
        model=gemini_model,
        system_prompt="""You are a technical documentation analyzer. Your task is to:
1. Analyze relationships between documentation pages
2. Group related pages by topic, API category, or conceptual similarity
3. Create logical, coherent groupings that make sense for developers

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
- Create 3-8 groups depending on content diversity
- Group related concepts together (e.g., all authentication pages, all API endpoints)
- Consider the logical flow developers would follow"""
    )
    
    # Prepare page summaries for analysis
    page_summaries = []
    for i, page in enumerate(pages):
        # Create a concise summary of each page
        content_preview = page.content[:500] if len(page.content) > 500 else page.content
        has_code = len(page.code_blocks) > 0
        
        page_summaries.append({
            "index": i,
            "url": page.url,
            "title": page.title,
            "content_preview": content_preview,
            "has_code_examples": has_code
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
    # Prepare content for summarization
    pages_content = []
    for page in pages:
        page_info = {
            "title": page.title,
            "url": page.url,
            "content": page.content[:2000],  # Limit content to avoid token limits
            "code_blocks": page.code_blocks[:5]  # Include up to 5 code blocks
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
4. Preserves and includes relevant code examples with proper markdown code blocks
5. Includes API signatures, function definitions, or important syntax
6. Uses proper markdown formatting:
   - Headings (##, ###) for sections
   - Code blocks with language tags (```python, ```javascript, etc.)
   - Lists for enumerating features or steps
   - Bold/italic for emphasis where appropriate
7. Provides sufficient context for AI coding assistants to help developers

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
