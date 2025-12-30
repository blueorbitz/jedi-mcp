"""Content processing and grouping using AI to organize documentation."""

import json
import logging
import re
import uuid
from typing import List, Dict, Set, Tuple, Optional
from strands import Agent

from .models import PageContent, ContentGroup, DocumentSection, EmbeddingConfig
from .model_config import create_content_processing_model
from .embedding_generator import EmbeddingGenerator
from .vector_database import VectorDatabaseManager

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


def process_content_with_embeddings(
    pages: List[PageContent], 
    project_name: str,
    db_manager: VectorDatabaseManager,
    embedding_config: Optional[EmbeddingConfig] = None
) -> List[ContentGroup]:
    """
    Process content with vector embeddings integration.
    
    Groups related pages, generates detailed summaries, creates embeddings,
    and stores everything in the vector database.
    
    Args:
        pages: List of crawled page content
        project_name: Name of the documentation project
        db_manager: Vector database manager for storage
        embedding_config: Optional embedding configuration
        
    Returns:
        List of ContentGroup objects with summaries and stored embeddings
        
    Requirements: 1.2, 6.1, 6.2
    """
    if not pages:
        logger.warning("No pages provided for content processing")
        return []
    
    logger.info(f"Processing {len(pages)} pages with embedding generation for project '{project_name}'")
    
    # Initialize embedding generator
    if embedding_config is None:
        embedding_config = EmbeddingConfig.from_env()
    
    embedding_generator = EmbeddingGenerator(embedding_config)
    
    # Initialize vector database schema
    db_manager.initialize_vector_schema(project_name, embedding_config)
    
    # First, do the regular content grouping
    content_groups = process_content(pages)
    
    # Now process each group with embeddings
    enhanced_groups = []
    
    for group in content_groups:
        logger.info(f"Generating embeddings for group '{group.name}'")
        
        # Generate vector-optimized summary and sections
        summary_markdown, document_sections = generate_searchable_summary(
            group.pages, group.name, f"Documentation group: {group.name}"
        )
        
        # Create document slug
        document_slug = _generate_document_slug(group.name, project_name)
        
        # Generate embedding for the main summary
        summary_embedding = embedding_generator.generate_embedding(summary_markdown)
        
        # Extract keywords and source URLs from pages
        keywords = extract_keywords_from_pages(group.pages)
        source_urls = [page.url for page in group.pages]
        
        # Store document embedding in database
        db_manager.store_document_embedding(
            slug=document_slug,
            project_name=project_name,
            title=group.name.replace('-', ' ').title(),
            summary_text=summary_markdown,
            embedding=summary_embedding,
            category=_determine_category(group.name, group.pages),
            keywords=keywords,
            source_urls=source_urls
        )
        
        # Generate and store section embeddings
        for i, section in enumerate(document_sections):
            section_embedding = embedding_generator.generate_embedding(section.content)
            
            db_manager.store_section_embedding(
                section_id=section.section_id,
                document_slug=document_slug,
                section_title=section.title,
                section_content=section.content,
                embedding=section_embedding,
                section_order=i
            )
        
        # Create enhanced content group
        enhanced_group = ContentGroup(
            name=group.name,
            summary_markdown=summary_markdown,
            pages=group.pages
        )
        enhanced_groups.append(enhanced_group)
        
        logger.info(f"Stored embeddings for document '{document_slug}' with {len(document_sections)} sections")
    
    logger.info(f"Completed embedding generation for {len(enhanced_groups)} content groups")
    return enhanced_groups


def _deduplicate_content(pages: List[PageContent]) -> List[PageContent]:
    """
    Remove duplicate content while preserving unique code examples and explanations.
    Prioritizes JavaScript, Python, and PHP code examples.
    
    This is a legacy function that now uses the enhanced deduplication.
    
    Args:
        pages: List of pages to deduplicate
        
    Returns:
        List of pages with duplicates removed but unique content preserved
    """
    return _deduplicate_content_with_context(pages)


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
    Generate a detailed markdown summary for a content group using vector-optimized approach.
    
    Args:
        agent: Strands SDK Agent for generating summaries
        group_name: Name of the content group
        group_description: Brief description of the group
        pages: Pages in this group
        
    Returns:
        Detailed markdown-formatted summary
    """
    # Use the new vector-optimized summary generation
    summary_markdown, _ = generate_searchable_summary(pages, group_name, group_description)
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


# Vector-optimized content processing functions

def generate_searchable_summary(pages: List[PageContent], group_name: str, group_description: str) -> Tuple[str, List[DocumentSection]]:
    """
    Generate vector-optimized summary with keyword integration and section breakdown.
    
    Args:
        pages: List of pages to summarize
        group_name: Name of the content group
        group_description: Description of the content group
        
    Returns:
        Tuple of (summary_markdown, document_sections)
        
    Requirements: 2.1, 2.2, 2.3
    """
    logger.info(f"Generating searchable summary for group '{group_name}' with {len(pages)} pages")
    
    # Create model for content processing
    model = create_content_processing_model()
    agent = Agent(model=model, system_prompt="""You are a technical documentation analyzer specialized in creating vector-search optimized summaries.""")
    
    # Deduplicate content while preserving context
    deduplicated_pages = _deduplicate_content_with_context(pages)
    
    # Extract keywords from all pages
    all_keywords = extract_keywords_from_pages(deduplicated_pages)
    
    # Generate the main summary with keyword integration
    summary_markdown = _generate_keyword_rich_summary(
        agent, group_name, group_description, deduplicated_pages, all_keywords
    )
    
    # Break down summary into sections with unique identifiers
    document_sections = create_document_sections(summary_markdown, all_keywords)
    
    logger.info(f"Generated summary with {len(document_sections)} sections and {len(all_keywords)} keywords")
    
    return summary_markdown, document_sections


def extract_keywords_from_pages(pages: List[PageContent]) -> List[str]:
    """
    Extract relevant keywords from page content for vector search optimization.
    
    Args:
        pages: List of pages to extract keywords from
        
    Returns:
        List of unique keywords sorted by relevance
        
    Requirements: 2.1
    """
    keyword_frequency = {}
    
    # Technical terms patterns
    technical_patterns = [
        r'\b[A-Z][a-zA-Z]*(?:[A-Z][a-zA-Z]*)*\b',  # CamelCase (API names, classes)
        r'\b[a-z]+(?:[A-Z][a-z]*)+\b',  # camelCase (functions, variables)
        r'\b[a-z]+(?:_[a-z]+)+\b',  # snake_case (functions, variables)
        r'\b[A-Z]+(?:_[A-Z]+)*\b',  # UPPER_CASE (constants)
        r'\b(?:GET|POST|PUT|DELETE|PATCH)\b',  # HTTP methods
        r'\b(?:JSON|XML|HTML|CSS|JavaScript|Python|PHP|SQL)\b',  # Technologies
        r'\b(?:API|SDK|CLI|URL|URI|HTTP|HTTPS)\b',  # Common acronyms
        r'\b(?:function|class|method|property|parameter|argument|return|response)\b',  # Programming terms
    ]
    
    for page in pages:
        # Combine title and content for keyword extraction
        text = f"{page.title} {page.content}"
        
        # Extract technical terms using patterns
        for pattern in technical_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                keyword = match.lower()
                if len(keyword) >= 3:  # Filter out very short terms
                    keyword_frequency[keyword] = keyword_frequency.get(keyword, 0) + 1
        
        # Extract quoted terms (often important concepts)
        quoted_terms = re.findall(r'"([^"]+)"', text)
        quoted_terms.extend(re.findall(r"'([^']+)'", text))
        for term in quoted_terms:
            if 3 <= len(term) <= 50:  # Reasonable length
                keyword = term.lower()
                keyword_frequency[keyword] = keyword_frequency.get(keyword, 0) + 2  # Higher weight
        
        # Extract code block content for API names and functions
        for code_block in page.code_blocks:
            # Look for function/method definitions
            func_matches = re.findall(r'(?:function|def|class)\s+([a-zA-Z_][a-zA-Z0-9_]*)', code_block)
            for func_name in func_matches:
                keyword_frequency[func_name.lower()] = keyword_frequency.get(func_name.lower(), 0) + 3
    
    # Sort keywords by frequency and relevance
    sorted_keywords = sorted(
        keyword_frequency.items(), 
        key=lambda x: x[1], 
        reverse=True
    )
    
    # Return top keywords, filtering out common words
    common_words = {
        'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 
        'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its', 'may', 'new', 'now', 'old', 
        'see', 'two', 'who', 'boy', 'did', 'she', 'use', 'her', 'way', 'many', 'then', 'them', 'well',
        'this', 'that', 'with', 'have', 'will', 'your', 'from', 'they', 'know', 'want', 'been', 'good',
        'much', 'some', 'time', 'very', 'when', 'come', 'here', 'just', 'like', 'long', 'make', 'over',
        'such', 'take', 'than', 'them', 'well', 'were'
    }
    
    filtered_keywords = [
        keyword for keyword, freq in sorted_keywords 
        if keyword not in common_words and len(keyword) >= 3
    ]
    
    return filtered_keywords[:50]  # Return top 50 keywords


def create_document_sections(summary_markdown: str, keywords: List[str]) -> List[DocumentSection]:
    """
    Break down summary into logical sections with unique identifiers.
    
    Args:
        summary_markdown: The complete summary markdown
        keywords: List of relevant keywords
        
    Returns:
        List of DocumentSection objects with unique IDs
        
    Requirements: 2.2
    """
    sections = []
    
    # Split by markdown headers (## and ###)
    header_pattern = r'^(#{2,3})\s+(.+)$'
    lines = summary_markdown.split('\n')
    
    current_section_title = None
    current_section_content = []
    current_section_level = 0
    
    for line in lines:
        header_match = re.match(header_pattern, line)
        
        if header_match:
            # Save previous section if it exists
            if current_section_title and current_section_content:
                section_text = '\n'.join(current_section_content).strip()
                if section_text:  # Only create section if it has content
                    section_keywords = _extract_section_keywords(section_text, keywords)
                    sections.append(DocumentSection(
                        section_id=_generate_section_id(current_section_title),
                        title=current_section_title,
                        content=section_text,
                        keywords=section_keywords
                    ))
            
            # Start new section
            header_level = len(header_match.group(1))
            current_section_title = header_match.group(2).strip()
            current_section_content = []
            current_section_level = header_level
        else:
            # Add line to current section
            current_section_content.append(line)
    
    # Don't forget the last section
    if current_section_title and current_section_content:
        section_text = '\n'.join(current_section_content).strip()
        if section_text:
            section_keywords = _extract_section_keywords(section_text, keywords)
            sections.append(DocumentSection(
                section_id=_generate_section_id(current_section_title),
                title=current_section_title,
                content=section_text,
                keywords=section_keywords
            ))
    
    # If no sections were found (no headers), create a single section
    if not sections and summary_markdown.strip():
        section_keywords = _extract_section_keywords(summary_markdown, keywords)
        sections.append(DocumentSection(
            section_id=str(uuid.uuid4()),
            title="Overview",
            content=summary_markdown.strip(),
            keywords=section_keywords
        ))
    
    return sections


def _deduplicate_content_with_context(pages: List[PageContent]) -> List[PageContent]:
    """
    Enhanced deduplication that preserves context and unique information.
    
    Args:
        pages: List of pages to deduplicate
        
    Returns:
        List of deduplicated pages with context preserved
        
    Requirements: 2.3
    """
    if not pages:
        return pages
    
    # Track content fingerprints and unique elements
    seen_content_hashes = set()
    seen_code_blocks = set()
    unique_pages = []
    
    for page in pages:
        # Create content fingerprint (first 300 chars, normalized)
        content_normalized = re.sub(r'\s+', ' ', page.content[:300]).strip().lower()
        content_hash = hash(content_normalized)
        
        # Check for unique code blocks
        unique_code_blocks = []
        for code_block in page.code_blocks:
            code_normalized = re.sub(r'\s+', ' ', code_block).strip()
            code_hash = hash(code_normalized)
            if code_hash not in seen_code_blocks:
                unique_code_blocks.append(code_block)
                seen_code_blocks.add(code_hash)
        
        # Keep page if it has unique content OR unique code blocks
        has_unique_content = content_hash not in seen_content_hashes
        has_unique_code = len(unique_code_blocks) > 0
        
        if has_unique_content or has_unique_code:
            # Preserve the page with prioritized code blocks
            prioritized_code = _prioritize_code_blocks(unique_code_blocks + page.code_blocks)
            
            # Remove duplicates from prioritized code while preserving order
            seen_in_this_page = set()
            final_code_blocks = []
            for code in prioritized_code:
                code_hash = hash(re.sub(r'\s+', ' ', code).strip())
                if code_hash not in seen_in_this_page:
                    final_code_blocks.append(code)
                    seen_in_this_page.add(code_hash)
            
            updated_page = PageContent(
                url=page.url,
                title=page.title,
                content=page.content,
                code_blocks=final_code_blocks[:10]  # Limit to top 10 code blocks
            )
            
            unique_pages.append(updated_page)
            seen_content_hashes.add(content_hash)
    
    logger.info(f"Deduplicated {len(pages)} pages to {len(unique_pages)} unique pages")
    return unique_pages


def _generate_keyword_rich_summary(
    agent: Agent,
    group_name: str,
    group_description: str,
    pages: List[PageContent],
    keywords: List[str]
) -> str:
    """
    Generate summary with integrated keywords for better vector search.
    
    Args:
        agent: Strands agent for content generation
        group_name: Name of the content group
        group_description: Description of the group
        pages: Deduplicated pages
        keywords: Extracted keywords
        
    Returns:
        Keyword-rich markdown summary
    """
    # Prepare content with keyword context
    pages_content = []
    for page in pages:
        prioritized_code_blocks = _prioritize_code_blocks(page.code_blocks[:8])
        
        page_info = {
            "title": page.title,
            "url": page.url,
            "content": page.content[:2500],  # Reasonable limit for context
            "code_blocks": prioritized_code_blocks
        }
        pages_content.append(page_info)
    
    # Create keyword context string
    keyword_context = ", ".join(keywords[:20])  # Top 20 keywords
    
    summary_prompt = f"""Create a comprehensive, vector-search optimized markdown summary for this documentation group.

Group: {group_name}
Description: {group_description}
Key Terms/Keywords: {keyword_context}

Pages in this group:
{json.dumps(pages_content, indent=2)}

Generate a detailed markdown summary that:

1. **KEYWORD INTEGRATION**: Naturally incorporate the key terms throughout the summary to improve semantic search
2. **STRUCTURED SECTIONS**: Use clear ## and ### headers to create logical sections
3. **COMPREHENSIVE COVERAGE**: Include all important concepts, APIs, functions, and procedures
4. **CODE EXAMPLES**: Preserve all unique code examples with proper language tags
5. **SEARCH OPTIMIZATION**: Write in a way that matches how developers would search for this information
6. **CONTEXT PRESERVATION**: Ensure each section can be understood independently
7. **TECHNICAL ACCURACY**: Maintain precise technical terminology and API signatures

Structure the summary with these sections as appropriate:
- ## Overview (what this covers, key concepts)
- ## Key Features/Components (main functionality)
- ## API Reference (if applicable - functions, methods, endpoints)
- ## Code Examples (practical usage examples)
- ## Configuration/Setup (if applicable)
- ## Best Practices (if applicable)

IMPORTANT GUIDELINES:
- Use the provided keywords naturally in context (don't force them)
- Prioritize JavaScript, Python, PHP code examples in that order
- Each section should be substantial enough to be useful for vector search
- Include specific function names, API endpoints, and technical terms
- Write for developers who need practical, actionable information
- Ensure the summary is comprehensive enough that developers rarely need to visit original pages

Return ONLY the markdown content."""
    
    summary_response = agent(summary_prompt)
    summary_markdown = str(summary_response).strip()
    
    # Ensure proper markdown structure
    if not summary_markdown.startswith('#'):
        summary_markdown = f"# {group_name.replace('-', ' ').title()}\n\n{summary_markdown}"
    
    return summary_markdown


def _extract_section_keywords(section_content: str, all_keywords: List[str]) -> List[str]:
    """
    Extract relevant keywords for a specific section.
    
    Args:
        section_content: Content of the section
        all_keywords: All available keywords
        
    Returns:
        List of keywords relevant to this section
    """
    section_lower = section_content.lower()
    relevant_keywords = []
    
    for keyword in all_keywords:
        if keyword.lower() in section_lower:
            relevant_keywords.append(keyword)
    
    return relevant_keywords[:10]  # Limit to top 10 relevant keywords


def _generate_section_id(section_title: str) -> str:
    """
    Generate a unique, URL-friendly section ID.
    
    Args:
        section_title: Title of the section
        
    Returns:
        Unique section identifier
    """
    # Create base ID from title
    base_id = re.sub(r'[^a-zA-Z0-9\s]', '', section_title)
    base_id = re.sub(r'\s+', '-', base_id.strip()).lower()
    
    # Add short UUID suffix for uniqueness
    unique_suffix = str(uuid.uuid4())[:8]
    
    return f"{base_id}-{unique_suffix}"


def _generate_document_slug(group_name: str, project_name: str) -> str:
    """
    Generate a unique document slug for database storage.
    
    Args:
        group_name: Name of the content group
        project_name: Name of the project
        
    Returns:
        Unique document slug
    """
    # Create base slug from group name
    base_slug = re.sub(r'[^a-zA-Z0-9\-]', '', group_name.lower())
    
    # Add project prefix and ensure uniqueness
    project_prefix = re.sub(r'[^a-zA-Z0-9]', '', project_name.lower())[:10]
    unique_suffix = str(uuid.uuid4())[:8]
    
    return f"{project_prefix}-{base_slug}-{unique_suffix}"


def _determine_category(group_name: str, pages: List[PageContent]) -> str:
    """
    Determine the category for a content group based on name and content.
    
    Args:
        group_name: Name of the content group
        pages: Pages in the group
        
    Returns:
        Category string
    """
    # Category mapping based on common patterns
    category_patterns = {
        'getting-started': 'Getting Started',
        'quickstart': 'Getting Started',
        'tutorial': 'Tutorial',
        'guide': 'Guide',
        'api': 'API Reference',
        'reference': 'Reference',
        'examples': 'Examples',
        'sample': 'Examples',
        'configuration': 'Configuration',
        'config': 'Configuration',
        'setup': 'Setup',
        'installation': 'Installation',
        'deployment': 'Deployment',
        'troubleshooting': 'Troubleshooting',
        'faq': 'FAQ',
        'advanced': 'Advanced',
        'concepts': 'Concepts',
        'overview': 'Overview'
    }
    
    # Check group name for category hints
    group_lower = group_name.lower()
    for pattern, category in category_patterns.items():
        if pattern in group_lower:
            return category
    
    # Check page URLs for category hints
    url_categories = []
    for page in pages:
        url_lower = page.url.lower()
        for pattern, category in category_patterns.items():
            if pattern in url_lower:
                url_categories.append(category)
    
    # Return most common category from URLs, or default
    if url_categories:
        from collections import Counter
        most_common = Counter(url_categories).most_common(1)
        return most_common[0][0]
    
    return 'Documentation'
