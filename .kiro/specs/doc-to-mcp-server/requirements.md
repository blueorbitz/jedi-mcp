# Requirements Document

## Introduction

The Jedi-MCP system is a Python-based CLI tool that converts technical documentation websites into Model Context Protocol (MCP) servers. The system uses AI to intelligently extract navigation links from documentation pages, crawls the identified pages, groups and summarizes content using the Strands SDK, stores the summaries as markdown files, and exposes each content group as an MCP tool. This enables AI coding assistants (Kiro, GitHub Copilot, Cursor, Windsurf, etc.) to provide developers with detailed framework, library, API, SDK, and language documentation context during development.

## Glossary

- **Jedi-MCP System**: The complete documentation-to-MCP server generator CLI application
- **CLI Command**: The command-line interface for generating MCP servers from documentation URLs
- **Navigation Extractor**: The AI-powered component that identifies and extracts documentation links from navigation/sidebar elements
- **Documentation Crawler**: The component responsible for fetching content from identified documentation pages
- **Strands SDK**: The external SDK used for intelligent content grouping and detailed summarization
- **Content Processor**: The component that processes crawled documentation using Strands SDK
- **Content Group**: A logical grouping of related documentation pages with a detailed summary in markdown format
- **SQLite Database**: The persistent storage system for content groups, markdown-formatted summaries, and page metadata
- **MCP Tool**: A Model Context Protocol tool that exposes a specific content group to AI coding assistants
- **MCP Server**: The Model Context Protocol server that exposes documentation tools to AI coding assistants
- **UV**: Python package manager used for dependency resolution and virtual environment management
- **Virtual Environment**: An isolated Python environment managed by UV's venv functionality

## Requirements

### Requirement 1

**User Story:** As a developer, I want to run a CLI command with a documentation URL and name, so that the system can generate an MCP server for that documentation.

#### Acceptance Criteria

1. WHEN a user executes the CLI command with URL and name parameters, THE CLI Command SHALL validate that both parameters are provided
2. WHEN the CLI Command receives valid parameters, THE CLI Command SHALL initiate the documentation generation process
3. WHEN the CLI Command completes successfully, THE CLI Command SHALL output a confirmation message with the generated MCP server location
4. WHEN the CLI Command encounters errors, THE CLI Command SHALL display clear error messages to the user
5. WHERE a user provides optional configuration flags, THE CLI Command SHALL pass those settings to the generation process

### Requirement 2

**User Story:** As a developer, I want the system to use AI to extract navigation links from the documentation page, so that only relevant documentation pages are crawled.

#### Acceptance Criteria

1. WHEN the Navigation Extractor receives the root documentation page, THE Navigation Extractor SHALL use Strands SDK to identify navigation or sidebar elements
2. WHEN the Navigation Extractor identifies navigation elements, THE Navigation Extractor SHALL extract all documentation links from those elements
3. WHEN the Navigation Extractor extracts links, THE Navigation Extractor SHALL filter out non-documentation links such as external sites or non-content pages
4. WHEN the Navigation Extractor completes extraction, THE Navigation Extractor SHALL return a list of documentation URLs to crawl

### Requirement 3

**User Story:** As a developer, I want the system to crawl the identified documentation pages, so that all relevant content is retrieved for processing.

#### Acceptance Criteria

1. WHEN the Documentation Crawler receives a list of URLs, THE Documentation Crawler SHALL fetch the content from each URL
2. WHEN the Documentation Crawler fetches a page, THE Documentation Crawler SHALL extract the main content while excluding navigation, footers, and other non-content elements
3. WHEN the Documentation Crawler encounters network errors or timeouts, THE Documentation Crawler SHALL retry the request up to three times before marking the page as failed
4. WHEN the Documentation Crawler completes crawling, THE Documentation Crawler SHALL return all successfully retrieved page content with their URLs and titles

### Requirement 4

**User Story:** As a developer, I want the system to intelligently group and summarize documentation content, so that related information is organized with detailed context for AI coding assistance.

#### Acceptance Criteria

1. WHEN the Content Processor receives crawled documentation pages, THE Content Processor SHALL use Strands SDK to analyze content relationships
2. WHEN the Content Processor identifies related content, THE Content Processor SHALL group pages into logical documentation sections
3. WHEN the Content Processor creates a group, THE Content Processor SHALL generate a detailed summary using Strands SDK that provides sufficient context for AI coding assistance
4. WHEN the Content Processor generates summaries, THE Content Processor SHALL include code examples, API signatures, and key concepts from the grouped content
5. WHEN the Content Processor completes processing, THE Content Processor SHALL return content groups with their detailed summaries

### Requirement 5

**User Story:** As a developer, I want content group summaries stored in SQLite in markdown format, so that the documentation is efficiently queryable and human-readable.

#### Acceptance Criteria

1. WHEN the Jedi-MCP System initializes for a documentation project, THE SQLite Database SHALL create the required schema if it does not exist
2. WHEN the Content Processor completes processing, THE Jedi-MCP System SHALL store all content groups with their summaries in the SQLite Database
3. WHEN storing a content group, THE Jedi-MCP System SHALL format the summary content using markdown syntax including headings, code blocks, and lists
4. WHEN storing a content group, THE Jedi-MCP System SHALL save the group name, markdown-formatted summary, and associated page URLs in the SQLite Database
5. WHEN storing content groups, THE Jedi-MCP System SHALL maintain relationships between groups and their source pages
6. WHEN the SQLite Database is queried, THE Jedi-MCP System SHALL retrieve content groups using indexed fields for efficient lookup

### Requirement 6

**User Story:** As a developer, I want each content group exposed as an MCP tool, so that AI coding assistants can access specific documentation sections through the Model Context Protocol.

#### Acceptance Criteria

1. WHEN the MCP Server initializes, THE MCP Server SHALL query the SQLite Database for all content groups
2. WHEN the MCP Server retrieves a content group, THE MCP Server SHALL create an MCP tool for that content group
3. WHEN creating an MCP tool, THE MCP Server SHALL use the content group name as the tool name and include a description based on the summary
4. WHEN an AI coding assistant invokes an MCP tool, THE MCP Server SHALL retrieve the full markdown summary from the SQLite Database and return it
5. WHEN the MCP Server starts, THE MCP Server SHALL register all content group tools with the MCP protocol

### Requirement 7

**User Story:** As a developer, I want to run the generated MCP server, so that AI coding assistants can connect and access the documentation tools.

#### Acceptance Criteria

1. WHEN a user starts the MCP Server for a documentation project, THE MCP Server SHALL initialize and listen for MCP protocol connections
2. WHEN an AI coding assistant connects to the MCP Server, THE MCP Server SHALL establish a valid MCP protocol session
3. WHEN the MCP Server receives a tool list request, THE MCP Server SHALL return all available content group tools
4. WHEN the MCP Server encounters errors during initialization or operation, THE MCP Server SHALL log clear error messages

### Requirement 8

**User Story:** As a developer, I want to manage the project using UV with virtual environments, so that dependencies are isolated and reproducible across different development environments.

#### Acceptance Criteria

1. WHEN a user initializes the project, THE Jedi-MCP System SHALL use UV to create a virtual environment
2. WHEN the Jedi-MCP System installs dependencies, THE Jedi-MCP System SHALL use UV to resolve and install all required Python packages into the virtual environment
3. WHEN a user runs any Jedi-MCP System command, THE Jedi-MCP System SHALL execute within the UV-managed virtual environment
4. WHEN the project configuration changes, THE Jedi-MCP System SHALL maintain a lock file that ensures reproducible dependency installation

### Requirement 9

**User Story:** As a developer, I want the system to handle various documentation formats, so that it can process different types of technical documentation websites.

#### Acceptance Criteria

1. WHEN the Documentation Crawler encounters HTML content, THE Documentation Crawler SHALL extract text content while preserving semantic structure
2. WHEN the Documentation Crawler encounters code blocks, THE Documentation Crawler SHALL preserve code formatting and syntax information
3. WHEN the Documentation Crawler encounters markdown-formatted content within HTML, THE Documentation Crawler SHALL parse and preserve the markdown structure
4. WHEN the Content Processor generates summaries, THE Content Processor SHALL preserve code examples in their original format within the markdown output
