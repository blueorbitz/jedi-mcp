# Development Guidelines for AI Agents

This document provides steering guidance for AI agents working on the Jedi-MCP codebase during development.

## Project Setup and Environment

### Rule
- Never read or edit the `.env`. Guide user what to change instead.

### Virtual Environment Management
```bash
# ALWAYS activate the virtual environment first
.venv\Scripts\Activate.ps1  # Windows PowerShell
# source .venv/bin/activate  # Linux/Mac

# Use uv for dependency management - NEVER use pip
uv sync                    # Install/sync dependencies
uv sync --extra dev       # Include development dependencies
uv sync --extra all       # Include all optional dependencies
```

### Dependency Management Rules
- **NEVER use `pip install`** - this project uses `uv` for package management
- **ALWAYS use `uv sync`** to install or update dependencies
- **Update pyproject.toml** for new dependencies, then run `uv sync`
- **Check uv.lock** is updated when dependencies change

### Testing Commands
```bash
# Run tests (after uv sync --extra dev)
python -m pytest tests/ -v

# Run specific test categories
python -m pytest tests/unit/ -v          # Unit tests
python -m pytest tests/property/ -v      # Property-based tests
python -m pytest tests/integration/ -v   # Integration tests

# Run with coverage
python -m pytest tests/ --cov=src/jedi_mcp --cov-report=html
```

## Architecture Overview

### Core Components
- **DatabaseManager** (`src/jedi_mcp/database.py`) - Base SQLite operations
- **VectorDatabaseManager** (`src/jedi_mcp/vector_database.py`) - Extends with vector capabilities
- **EmbeddingGenerator** (`src/jedi_mcp/embedding_generator.py`) - Text embedding generation
- **ContentProcessor** (`src/jedi_mcp/content_processor.py`) - AI-powered content processing
- **MCP Server** (`src/jedi_mcp/mcp_server.py`) - Model Context Protocol server

### Database Schema
- **projects** table - Project metadata with embedding configuration
- **content_groups** table - Logical groupings of documentation
- **pages** table - Individual crawled pages
- **document_embeddings** table - Vector embeddings for semantic search
- **section_embeddings** table - Section-level embeddings

### Import Organization
```python
# Standard library imports
import os
import json
from pathlib import Path
from typing import List, Optional, Dict

# Third-party imports
import sqlite3
from sentence_transformers import SentenceTransformer

# Local imports
from .models import EmbeddingConfig, SearchResult
from .database import DatabaseManager
```

### Database Schema Changes
1. Update schema in `VectorDatabaseManager.initialize_vector_schema()`
2. Handle existing databases gracefully (check column existence)
3. Add migration logic if needed
4. Update models in `models.py` if necessary
5. Write tests for new schema elements

### Implementing MCP Tools
1. Follow the pattern in `src/jedi_mcp/mcp_server.py`
2. Use `@mcp.tool()` decorator with clear descriptions
3. Validate input parameters
4. Return structured, well-formatted responses
5. Handle errors gracefully with meaningful messages
