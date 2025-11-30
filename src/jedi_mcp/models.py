"""Data models for the Jedi-MCP system."""

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
