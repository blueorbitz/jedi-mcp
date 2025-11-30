# Implementation Plan

- [x] 1. Set up project structure and dependencies





  - Initialize UV project with pyproject.toml
  - Configure Python 3.10+ with virtual environment
  - Add core dependencies: strands-agents, fastmcp, httpx, beautifulsoup4, click, lxml
  - Add dev dependencies: pytest, hypothesis, responses, pytest-asyncio
  - Create src/jedi_mcp package structure with __init__.py
  - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [x] 2. Implement data models and database schema







  - [x] 2.1 Create data models in models.py

    - Define DocumentationLink dataclass with url, title, category fields
    - Define PageContent dataclass with url, title, content, code_blocks fields
    - Define ContentGroup dataclass with name, summary_markdown, pages fields
    - Define CrawlConfig dataclass with rate_limit_delay, max_retries, timeout, custom_headers fields

    - Define GenerationResult dataclass for CLI output
    - _Requirements: 5.1, 5.4_
  - [x] 2.2 Implement DatabaseManager class in database.py

    - Create initialize_schema method to create tables (projects, content_groups, pages)
    - Add indexes for project_id and content_group_id
    - Implement store_content_group method with transaction support
    - Implement get_all_content_groups method
    - Implement get_content_group_by_name method
    - Use parameterized queries for SQL injection prevention
    - _Requirements: 5.1, 5.2, 5.4, 5.5, 5.6_
  - [ ]* 2.3 Write property test for schema initialization
    - **Property 10: Schema initialization**
    - **Validates: Requirements 5.1**
  - [ ]* 2.4 Write property test for storage completeness
    - **Property 11: Storage completeness**
    - **Validates: Requirements 5.2, 5.4, 5.5**
  - [ ]* 2.5 Write property test for markdown formatting
    - **Property 12: Markdown formatting in storage**
    - **Validates: Requirements 5.3**

- [x] 3. Implement HTML content extraction and crawling





  - [x] 3.1 Create Documentation Crawler in crawler.py


    - Implement crawl_pages function with httpx async client
    - Add retry decorator with max 3 retries and exponential backoff
    - Implement rate limiting using asyncio.sleep
    - Extract main content using BeautifulSoup, excluding nav/footer/aside elements
    - Preserve code blocks (pre, code tags) with formatting
    - Extract page title from h1 or title tag
    - Handle network errors with clear error messages
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 9.1, 9.2, 9.3_
  - [ ]* 3.2 Write property test for content extraction
    - **Property 5: Content extraction excludes non-content elements**
    - **Validates: Requirements 3.2**
  - [ ]* 3.3 Write property test for retry behavior
    - **Property 6: Retry behavior on network errors**
    - **Validates: Requirements 3.3**
  - [ ]* 3.4 Write property test for crawl result completeness
    - **Property 7: Crawl result completeness**
    - **Validates: Requirements 3.4**
  - [ ]* 3.5 Write property test for HTML structure preservation
    - **Property 17: HTML semantic structure preservation**
    - **Validates: Requirements 9.1**
  - [ ]* 3.6 Write property test for code block preservation
    - **Property 18: Code block format preservation**
    - **Validates: Requirements 9.2**
  - [ ]* 3.7 Write property test for markdown preservation
    - **Property 19: Markdown structure preservation**
    - **Validates: Requirements 9.3**

- [ ] 4. Implement AI-powered navigation extraction
  - [ ] 4.1 Create Navigation Extractor in navigation_extractor.py
    - Implement extract_navigation_links function
    - Use Strands SDK Agent to analyze HTML and identify navigation elements
    - Create prompt for agent to extract documentation links from nav/sidebar
    - Filter out external links (different domain)
    - Filter out non-documentation links (social media, login, search)
    - Resolve relative URLs to absolute URLs
    - Return list of DocumentationLink objects
    - _Requirements: 2.1, 2.2, 2.3, 2.4_
  - [ ]* 4.2 Write property test for navigation extraction
    - **Property 4: Navigation link extraction completeness**
    - **Validates: Requirements 2.2, 2.3**

- [ ] 5. Implement content processing and grouping
  - [ ] 5.1 Create Content Processor in content_processor.py
    - Implement process_content function
    - Use Strands SDK Agent to analyze content relationships between pages
    - Create prompt for agent to group related pages by topic/category
    - Generate detailed markdown summaries for each group using Strands SDK
    - Ensure summaries include code examples, API signatures, and key concepts
    - Format summaries with proper markdown syntax (headings, code blocks, lists)
    - Return list of ContentGroup objects
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 9.4_
  - [ ]* 5.2 Write property test for content grouping
    - **Property 8: Content grouping with summaries**
    - **Validates: Requirements 4.2, 4.3, 4.5**
  - [ ]* 5.3 Write property test for summary content preservation
    - **Property 9: Summary content preservation**
    - **Validates: Requirements 4.4, 9.4**

- [ ] 6. Implement MCP server with dynamic tool registration
  - [ ] 6.1 Create MCP Server in mcp_server.py
    - Implement create_mcp_server function using FastMCP
    - Query database for all content groups on initialization
    - Dynamically register MCP tools for each content group
    - Sanitize content group names for MCP tool name compatibility
    - Generate tool descriptions from summary excerpts (first 100 chars)
    - Implement tool functions that retrieve markdown from database
    - Add error handling and logging for tool invocation
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 7.1, 7.2, 7.3, 7.4_
  - [ ]* 6.2 Write property test for tool creation
    - **Property 13: Tool creation from content groups**
    - **Validates: Requirements 6.2, 6.3, 6.5**
  - [ ]* 6.3 Write property test for tool invocation
    - **Property 14: Tool invocation returns markdown**
    - **Validates: Requirements 6.4**
  - [ ]* 6.4 Write property test for tool list completeness
    - **Property 15: Tool list completeness**
    - **Validates: Requirements 7.3**
  - [ ]* 6.5 Write property test for error logging
    - **Property 16: Error logging**
    - **Validates: Requirements 7.4**

- [ ] 7. Implement CLI command interface
  - [ ] 7.1 Create CLI in cli.py
    - Implement main CLI using Click framework
    - Add generate command with --url and --name required parameters
    - Add optional --rate-limit, --max-retries, --timeout flags
    - Validate URL format (http/https scheme)
    - Validate project name (alphanumeric, hyphens, underscores only)
    - Orchestrate pipeline: navigation extraction → crawling → processing → storage
    - Initialize database for project
    - Display progress indicators during generation
    - Output confirmation message with database location on success
    - Display clear error messages on failure
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_
  - [ ] 7.2 Add serve command to run MCP server
    - Implement serve command with --project required parameter
    - Validate project exists in database
    - Create and start MCP server for project
    - Handle graceful shutdown on SIGINT/SIGTERM
    - _Requirements: 7.1, 7.2_
  - [ ]* 7.3 Write property test for CLI validation
    - **Property 1: CLI parameter validation**
    - **Validates: Requirements 1.1, 1.4**
  - [ ]* 7.4 Write property test for configuration propagation
    - **Property 2: Configuration propagation**
    - **Validates: Requirements 1.5**
  - [ ]* 7.5 Write property test for successful output
    - **Property 3: Successful generation output**
    - **Validates: Requirements 1.3**

- [ ] 8. Add entry point and packaging configuration
  - Configure pyproject.toml with console_scripts entry point for jedi-mcp CLI
  - Add project metadata (description, authors, license)
  - Configure build system with setuptools
  - _Requirements: 1.1_

- [ ] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ]* 10. Create integration tests
  - Write end-to-end test for complete pipeline (CLI → database → MCP server)
  - Test MCP server connection and tool invocation with FastMCP client
  - Test with real documentation URL (use small test site)
  - Verify database persistence and retrieval
  - _Requirements: All_

- [ ]* 11. Add documentation and examples
  - Create README.md with installation instructions
  - Add usage examples for generate and serve commands
  - Document configuration options
  - Add example MCP server connection in Kiro/Cursor/Copilot
  - Create CONTRIBUTING.md for development setup

- [ ] 12. Clean up all the temporary test file