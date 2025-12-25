# Implementation Plan: Vector Search Enhancement

## Overview

This implementation plan transforms the existing Jedi MCP system into a vector-enabled semantic search platform. The approach extends the current SQLite database with sqlite-vec, implements sentence-transformers for embeddings, and replaces individual content group tools with three comprehensive search and retrieval tools.

## Tasks

- [x] 1. Set up vector database infrastructure
  - Install and configure sqlite-vec extension for vector operations
  - Create embedding configuration management system
  - Extend database schema with vector tables and project embedding settings
  - _Requirements: 1.1, 1.2_

- [ ]* 1.1 Write property test for vector database initialization
  - **Property 6: Vector Database Storage and Search**
  - **Validates: Requirements 1.2, 1.3**

- [x] 2. Implement embedding generation system
  - [x] 2.1 Create EmbeddingGenerator class with sentence-transformers support
    - Support all-MiniLM-L6-v2 and Qwen3-Embedding-0.6B models
    - Implement batch processing and dynamic dimension handling
    - Add environment variable configuration loading
    - _Requirements: 2.1, 2.2_

  - [x] 2.2 Extend VectorDatabaseManager with embedding operations
    - Add methods for storing and retrieving embeddings
    - Implement project embedding configuration persistence
    - Add vector similarity search functionality
    - _Requirements: 1.2, 1.3, 6.1, 6.2_

- [ ]* 2.3 Write property test for embedding generation and storage
  - **Property 6: Vector Database Storage and Search**
  - **Validates: Requirements 1.2, 1.3**

- [x] 3. Enhance content processing for vector search
  - [x] 3.1 Extend ContentProcessor with vector-optimized summary generation
    - Implement keyword extraction and integration
    - Add document section breakdown with unique identifiers
    - Create deduplication while preserving context
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 3.2 Integrate embedding generation into content processing pipeline
    - Generate embeddings for document summaries and sections
    - Store embeddings with proper metadata and relationships
    - _Requirements: 1.2, 6.1, 6.2_

- [ ]* 3.3 Write property test for enhanced summary generation
  - **Property 1: Summary Generation with Keywords and Sections**
  - **Validates: Requirements 2.1, 2.2, 2.3**

- [x] 4. Checkpoint - Ensure vector infrastructure tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement searchDoc MCP tool
  - [x] 5.1 Create semantic search functionality
    - Implement vector similarity search with query embedding generation
    - Add result ranking and relevance scoring
    - Support both semantic and hybrid keyword-vector search
    - _Requirements: 3.1, 3.2, 3.4_

  - [x] 5.2 Implement search result formatting and filtering
    - Return structured results with slugs, titles, scores, and previews
    - Add project and category filtering capabilities
    - Handle edge cases like no results found
    - _Requirements: 3.2, 3.3_

- [ ]* 5.3 Write property test for comprehensive search functionality
  - **Property 2: Comprehensive Search Functionality**
  - **Validates: Requirements 3.1, 3.2, 3.4**

- [x] 6. Implement loadDoc MCP tool
  - [x] 6.1 Create document loading by slug functionality
    - Implement slug-based document retrieval
    - Add metadata inclusion (source URLs, dates, categories)
    - Support batch loading of multiple documents
    - _Requirements: 4.1, 4.3, 4.4_

  - [x] 6.2 Implement error handling for invalid slugs
    - Return appropriate error messages for invalid slugs
    - Provide suggested alternatives when possible
    - _Requirements: 4.2_

- [ ]* 6.3 Write property test for comprehensive document loading
  - **Property 3: Comprehensive Document Loading**
  - **Validates: Requirements 4.1, 4.3, 4.4**

- [x] 7. Implement listDoc MCP tool
  - [x] 7.1 Create documentation topic listing functionality
    - Return structured list of all available topics and categories
    - Include topic names, descriptions, document counts, and hierarchies
    - _Requirements: 5.1, 5.2_

  - [x] 7.2 Add filtering and organization capabilities
    - Support filtering by project, category, or content type
    - Implement clear navigation structure and grouping
    - _Requirements: 5.2, 5.4_

- [ ]* 7.3 Write property test for document listing format
  - **Property 4: Document Listing Format**
  - **Validates: Requirements 5.2, 5.4**

- [-] 8. Update MCP server to use new vector-enabled tools
  - [ ] 8.1 Replace existing content group tools with new vector tools
    - Remove individual content group tool registration
    - Register searchDoc, loadDoc, and listDoc tools
    - Ensure proper tool descriptions and parameter validation
    - _Requirements: 3.1, 4.1, 5.1_

  - [ ] 8.2 Implement project embedding configuration loading during server startup
    - Load stored embedding model settings from database
    - Initialize embedding generator with project-specific configuration
    - Ensure consistency between generation and serving phases
    - _Requirements: 1.2, 6.1, 6.2_

- [ ]* 8.3 Write property test for data organization and relationships
  - **Property 5: Data Organization and Relationships**
  - **Validates: Requirements 6.1, 6.2**

- [ ] 9. Update CLI commands for vector search support
  - [ ] 9.1 Enhance generate command with embedding configuration
    - Add environment variable reading for embedding model selection
    - Store embedding configuration in database during generation
    - Update content processing pipeline to include vector generation
    - _Requirements: 1.1, 1.2, 2.1_

  - [ ] 9.2 Update serve command for vector-enabled MCP server
    - Load project embedding configuration from database
    - Initialize vector-enabled MCP server with proper tools
    - Ensure embedding model consistency between generation and serving
    - _Requirements: 1.3, 3.1, 4.1, 5.1_

- [ ]* 9.3 Write unit tests for CLI command enhancements
  - Test environment variable configuration loading
  - Test embedding model validation and storage
  - Test vector-enabled server initialization

- [ ] 10. Add required dependencies and configuration
  - [ ] 10.1 Update pyproject.toml with new dependencies
    - Add sqlite-vec Python bindings
    - Add sentence-transformers library
    - Update development dependencies for property testing
    - _Requirements: 1.1, 2.1_

  - [ ] 10.2 Create example .env configuration file
    - Document available embedding models and their dimensions
    - Provide clear configuration examples
    - Add configuration validation and error messages
    - _Requirements: 2.1_

- [ ] 11. Final checkpoint - Ensure all tests pass and integration works
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- The implementation replaces existing content group tools with semantic search capabilities
- Embedding model configuration is stored in database for consistency between generation and serving phases