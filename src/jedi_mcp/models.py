"""Data models for the Jedi-MCP system."""

import os
from dataclasses import dataclass, field
from typing import List, Optional, Dict


@dataclass
class DocumentationLink:
    """Represents a documentation link extracted from navigation."""
    url: str
    title: Optional[str] = None
    category: Optional[str] = None


@dataclass
class PageContent:
    """Represents the content of a crawled documentation page."""
    url: str
    title: str
    content: str
    code_blocks: List[str] = field(default_factory=list)


@dataclass
class ContentGroup:
    """Represents a logical grouping of related documentation pages."""
    name: str
    summary_markdown: str
    pages: List[PageContent] = field(default_factory=list)


@dataclass
class CrawlConfig:
    """Configuration for documentation crawling behavior."""
    rate_limit_delay: float = 0.5
    max_retries: int = 3
    timeout: int = 30
    custom_headers: Optional[Dict[str, str]] = None


@dataclass
class GenerationResult:
    """Result of MCP server generation process."""
    success: bool
    message: str
    database_path: Optional[str] = None
    project_name: Optional[str] = None


@dataclass
class EmbeddingConfig:
    """Configuration for embedding generation."""
    provider: str = "sentence-transformers"
    model: str = "all-MiniLM-L6-v2"
    dimension: int = 384
    batch_size: int = 100
    max_text_length: int = 8000
    chunk_overlap: int = 200
    
    @classmethod
    def from_env(cls) -> 'EmbeddingConfig':
        """Load configuration from environment variables."""
        model = os.getenv('JEDI_EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
        
        # Determine dimension based on model
        dimension_map = {
            'all-MiniLM-L6-v2': 384,
            'Qwen/Qwen3-Embedding-0.6B': 1024
        }
        dimension = dimension_map.get(model, 384)
        
        return cls(provider="sentence-transformers", model=model, dimension=dimension)


@dataclass
class SearchResult:
    """Result from vector search operations."""
    slug: str
    title: str
    category: str
    relevance_score: float
    content_preview: str
    section_matches: List['SectionMatch'] = field(default_factory=list)


@dataclass
class SectionMatch:
    """Match within a document section."""
    section_id: str
    section_title: str
    content_snippet: str
    relevance_score: float


@dataclass
class DocumentSummary:
    """Complete document summary with metadata."""
    slug: str
    title: str
    category: str
    full_summary: str
    source_urls: List[str]
    created_at: str
    sections: List['DocumentSection'] = field(default_factory=list)


@dataclass
class DocumentSection:
    """Section within a document."""
    section_id: str
    title: str
    content: str
    keywords: List[str] = field(default_factory=list)


@dataclass
class DocumentMetadata:
    """Metadata for document listing."""
    slug: str
    title: str
    category: str
    description: str
    document_count: int
    last_updated: str
