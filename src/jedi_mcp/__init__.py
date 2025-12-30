"""
Jedi-MCP: Convert technical documentation websites into MCP servers.

This package provides tools to crawl documentation websites, intelligently
group and summarize content using AI, and expose the documentation as
Model Context Protocol (MCP) tools for AI coding assistants.
"""

__version__ = "0.1.0"

from .models import (
    EmbeddingConfig,
    SearchResult,
    SectionMatch,
    DocumentSummary,
    DocumentSection,
    DocumentMetadata
)
from .vector_database import VectorDatabaseManager
from .embedding_generator import EmbeddingGenerator

__all__ = [
    "EmbeddingConfig",
    "SearchResult", 
    "SectionMatch",
    "DocumentSummary",
    "DocumentSection",
    "DocumentMetadata",
    "VectorDatabaseManager",
    "EmbeddingGenerator"
]
