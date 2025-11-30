# Jedi-MCP Technical Architecture

## Overview

Jedi-MCP is a Python-based system that transforms technical documentation websites into Model Context Protocol (MCP) servers. It enables AI coding assistants to access detailed framework, library, API, and SDK documentation during development.

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI Interface                           │
│                      (jedi_mcp/cli.py)                          │
└────────────┬────────────────────────────────────┬───────────────┘
             │                                    │
             │ generate                           │ serve
             ▼                                    ▼
┌────────────────────────────┐      ┌────────────────────────────┐
│   Documentation Pipeline   │      │      MCP Server            │
│                            │      │   (mcp_server.py)          │
│  1. Navigation Extraction  │      │                            │
│  2. Content Crawling       │      │  ┌──────────────────────┐  │
│  3. Content Processing     │      │  │  FastMCP Framework   │  │
│  4. Database Storage       │      │  └──────────────────────┘  │
└────────────┬───────────────┘      └────────────┬───────────────┘
             │                                    │
             │                                    │
             ▼                                    ▼
┌────────────────────────────────────────────────────────────────┐
│                    SQLite Database                             │
│                   (database.py)                                │
│                                                                │
│  ┌──────────┐  ┌──────────────┐  ┌─────────────────────────┐   │
│  │ Projects │  │ Content      │  │ Pages                   │   │
│  │          │  │ Groups       │  │                         │   │
│  └──────────┘  └──────────────┘  └─────────────────────────┘   │
└────────────────────────────────────────────────────────────────┘
```

### Component Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Core Components                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌────────────────────┐         ┌────────────────────┐          │
│  │ Navigation         │         │ Content            │          │
│  │ Extractor          │         │ Crawler            │          │
│  │                    │         │                    │          │
│  │ • Smart DOM Parser │         │ • HTTP Client      │          │
│  │ • AI Fallback      │         │ • BeautifulSoup    │          │
│  │ • Browser Support  │         │ • Rate Limiting    │          │
│  └────────────────────┘         └────────────────────┘          │
│                                                                 │
│  ┌────────────────────┐         ┌────────────────────┐          │
│  │ Content            │         │ Database           │          │
│  │ Processor          │         │ Manager            │          │
│  │                    │         │                    │          │
│  │ • AI Grouping      │         │ • SQLite ORM       │          │
│  │ • Summary Gen      │         │ • CRUD Operations  │          │
│  │ • Strands Agent    │         │ • Schema Mgmt      │          │
│  └────────────────────┘         └────────────────────┘          │
│                                                                 │
│  ┌────────────────────┐         ┌────────────────────┐          │
│  │ MCP Server         │         │ CLI Interface      │          │
│  │                    │         │                    │          │
│  │ • FastMCP          │         │ • Click Framework  │          │
│  │ • Tool Registry    │         │ • Command Routing  │          │
│  │ • Transport Layer  │         │ • Validation       │          │
│  └────────────────────┘         └────────────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. CLI Interface (`cli.py`)

**Purpose**: Command-line interface for user interaction

**Key Functions**:
- `generate`: Orchestrates the documentation processing pipeline
- `serve`: Starts the MCP server for a processed project

**Commands**:
```bash
jedi-mcp generate --url <URL> --name <PROJECT>
jedi-mcp serve --project <PROJECT> [--transport stdio|sse]
```

**Validation**:
- URL format validation (http/https)
- Project name validation (alphanumeric, hyphens, underscores)
- Database existence checks

### 2. Navigation Extractor (`navigation_extractor.py`, `smart_navigation_extractor.py`)

**Purpose**: Extract documentation links from website navigation

**Extraction Strategies**:

1. **Smart DOM Parsing** (Primary)
   - Pattern-based sidebar detection
   - Docusaurus-specific extraction
   - Generic navigation parsing
   - No AI required, fast execution

2. **AI-Based Extraction** (Fallback)
   - Uses Google Gemini via Strands SDK
   - Handles complex/unusual navigation structures
   - JSON-based link extraction

3. **Browser-Based Extraction** (Optional)
   - Uses Playwright for JavaScript-rendered content
   - Headless browser automation
   - Waits for dynamic content loading

**Output**: List of `DocumentationLink` objects with URL, title, and category

### 3. Content Crawler (`crawler.py`)

**Purpose**: Fetch and extract content from documentation pages

**Features**:
- Asynchronous HTTP requests using `httpx`
- Exponential backoff retry mechanism
- Rate limiting between requests
- Content extraction using BeautifulSoup

**Content Extraction**:
- Removes navigation, footer, header, aside elements
- Extracts main content from `<main>`, `<article>`, or `<body>`
- Preserves code blocks separately
- Extracts page titles from `<h1>` or `<title>`

**Configuration** (`CrawlConfig`):
- `rate_limit_delay`: Delay between requests (default: 0.5s)
- `max_retries`: Maximum retry attempts (default: 3)
- `timeout`: Request timeout (default: 30s)
- `custom_headers`: Optional HTTP headers

### 4. Content Processor (`content_processor.py`)

**Purpose**: Group related pages and generate summaries using AI

**AI Integration**:
- Uses Google Gemini 2.5 Flash via Strands SDK
- Temperature: 0.3 for consistent grouping
- Max tokens: 8192 for detailed summaries

**Processing Pipeline**:

1. **Page Analysis**
   - Creates concise summaries of each page
   - Identifies code examples
   - Prepares metadata for AI analysis

2. **Content Grouping**
   - AI analyzes relationships between pages
   - Groups by topic, API category, or conceptual similarity
   - Creates 3-8 logical groups
   - Fallback: URL-based grouping if AI fails

3. **Summary Generation**
   - Generates detailed markdown summaries per group
   - Includes code examples with proper formatting
   - Preserves API signatures and syntax
   - Structured with headings, lists, and emphasis

**Output**: List of `ContentGroup` objects with name, summary, and pages

### 5. Database Manager (`database.py`)

**Purpose**: Persistent storage for processed documentation

**Database Schema**:

```sql
projects
├── id (INTEGER PRIMARY KEY)
├── name (TEXT UNIQUE)
├── root_url (TEXT)
└── created_at (TIMESTAMP)

content_groups
├── id (INTEGER PRIMARY KEY)
├── project_id (INTEGER FK)
├── name (TEXT)
├── summary_markdown (TEXT)
└── created_at (TIMESTAMP)

pages
├── id (INTEGER PRIMARY KEY)
├── content_group_id (INTEGER FK)
├── url (TEXT)
├── title (TEXT)
└── content (TEXT)
```

**Key Operations**:
- `initialize_schema()`: Creates tables and indexes
- `store_content_group()`: Stores groups and pages
- `get_all_content_groups()`: Retrieves all groups for a project
- `get_content_group_by_name()`: Retrieves specific group

**Storage Location**: `~/.jedi-mcp/jedi-mcp.db` (default)

### 6. MCP Server (`mcp_server.py`)

**Purpose**: Expose documentation as MCP tools

**Architecture**:
- Built on FastMCP framework
- Dynamic tool registration based on database content
- Each content group becomes an MCP tool

**Tool Generation**:
1. Sanitize group names for MCP compatibility
2. Generate tool descriptions from summaries
3. Create closure-based tool handlers
4. Register tools with FastMCP

**Tool Naming**:
- Lowercase with underscores and hyphens
- Alphanumeric characters only
- Prepends `doc_` if starts with non-letter

**Transport Options**:
- **stdio**: Standard input/output for MCP clients (default)
- **sse**: Server-Sent Events for HTTP/browser access

**Server Lifecycle**:
```python
create_mcp_server() → FastMCP instance
  ↓
Query database for content groups
  ↓
Register tool for each group
  ↓
run_mcp_server() → Start with transport
```

## Data Models (`models.py`)

### DocumentationLink
```python
@dataclass
class DocumentationLink:
    url: str
    title: Optional[str]
    category: Optional[str]
```

### PageContent
```python
@dataclass
class PageContent:
    url: str
    title: str
    content: str
    code_blocks: List[str]
```

### ContentGroup
```python
@dataclass
class ContentGroup:
    name: str
    summary_markdown: str
    pages: List[PageContent]
```

### CrawlConfig
```python
@dataclass
class CrawlConfig:
    rate_limit_delay: float = 0.5
    max_retries: int = 3
    timeout: int = 30
    custom_headers: Optional[Dict[str, str]] = None
```

## Technology Stack

### Core Dependencies

| Library | Version | Purpose |
|---------|---------|---------|
| Python | ≥3.10 | Runtime environment |
| strands-agents | ≥0.1.0 | AI agent framework |
| fastmcp | ≥0.1.0 | MCP server framework |
| httpx | ≥0.24.0 | Async HTTP client |
| beautifulsoup4 | ≥4.12.0 | HTML parsing |
| lxml | ≥4.9.0 | XML/HTML parser |
| click | ≥8.1.0 | CLI framework |
| python-dotenv | ≥1.0.0 | Environment variables |
| playwright | ≥1.40.0 | Browser automation (optional) |

### Development Dependencies

| Library | Version | Purpose |
|---------|---------|---------|
| pytest | ≥7.4.0 | Testing framework |
| hypothesis | ≥6.82.0 | Property-based testing |
| responses | ≥0.23.0 | HTTP mocking |
| pytest-asyncio | ≥0.21.0 | Async test support |

## Data Flow

### Generation Pipeline

```
1. User Input
   └─> URL + Project Name

2. Navigation Extraction
   └─> HTML Fetch → DOM Parsing → Link List

3. Content Crawling
   └─> Parallel Fetch → Content Extraction → Page List

4. Content Processing
   └─> AI Grouping → Summary Generation → Content Groups

5. Database Storage
   └─> Schema Init → Store Groups → Store Pages

6. Completion
   └─> Success Message + Database Path
```

### Serving Pipeline

```
1. User Input
   └─> Project Name + Transport Type

2. Database Query
   └─> Load Project → Load Content Groups

3. MCP Server Creation
   └─> Initialize FastMCP → Register Tools

4. Tool Registration
   └─> For each group:
       ├─> Sanitize name
       ├─> Generate description
       └─> Create handler closure

5. Server Start
   └─> stdio: Standard I/O
       └─> sse: HTTP Server on host:port

6. Tool Invocation
   └─> Client calls tool → Handler queries DB → Returns markdown
```

## AI Integration

### Google Gemini Configuration

**Model**: `gemini-2.5-flash`

**Navigation Extraction**:
- Temperature: 0.1 (deterministic)
- Max tokens: 8192
- Top-p: 0.95
- Purpose: Extract navigation links from HTML

**Content Grouping**:
- Temperature: 0.3 (consistent)
- Max tokens: 8192
- Top-p: 0.9
- Purpose: Analyze page relationships and create groups

**Summary Generation**:
- Temperature: 0.3 (consistent)
- Max tokens: 8192
- Top-p: 0.9
- Purpose: Generate detailed markdown summaries

### Strands SDK Integration

**Agent Creation**:
```python
agent = Agent(
    model=gemini_model,
    system_prompt="<task-specific prompt>"
)
```

**Usage Pattern**:
```python
response = agent(prompt)
result = str(response)
```

## Error Handling

### Network Errors
- Exponential backoff retry (1s, 2s, 4s)
- Configurable max retries
- Graceful degradation (skip failed pages)

### AI Failures
- Fallback to rule-based extraction
- URL-based grouping fallback
- JSON parsing error handling

### Database Errors
- Transaction rollback on failure
- Connection context management
- Schema validation

### Validation Errors
- URL format validation
- Project name validation
- Database existence checks

## Security Considerations

### Input Validation
- URL scheme validation (http/https only)
- Project name sanitization
- SQL injection prevention (parameterized queries)

### External Link Filtering
- Domain validation
- Social media link exclusion
- Authentication page exclusion

### API Key Management
- Environment variable storage
- `.env` file support
- No hardcoded credentials

## Performance Optimization

### Crawling
- Asynchronous HTTP requests
- Configurable rate limiting
- Connection pooling via httpx

### Database
- Indexed foreign keys
- Batch insertions
- Connection pooling

### AI Processing
- Content truncation (2000 chars per page)
- Limited code blocks (5 per page)
- Efficient prompt design

## Deployment Considerations

### System Requirements
- Python 3.10 or higher
- UV package manager
- Google Gemini API key
- Optional: Playwright for browser automation

### Installation
```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
uv pip install 'strands-agents[gemini]'
```

### Configuration
- Environment: `GOOGLE_API_KEY`
- Database: `~/.jedi-mcp/jedi-mcp.db`
- Custom paths supported via CLI flags

### MCP Client Integration

**Kiro IDE** (`.kiro/settings/mcp.json`):
```json
{
  "mcpServers": {
    "jedi-mcp": {
      "command": "jedi-mcp",
      "args": ["serve", "--project", "example-docs"],
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

**MCP Inspector**:
```bash
# Method 1: Direct connection
jedi-mcp serve --project example-docs --transport sse --port 8000
npx @modelcontextprotocol/inspector

# Method 2: Auto-launch
npx @modelcontextprotocol/inspector jedi-mcp serve --project example-docs
```

## Testing Strategy

### Unit Tests
- Component isolation
- Mock external dependencies
- Test data models and utilities

### Integration Tests
- End-to-end pipeline testing
- Database operations
- MCP server functionality

### Property-Based Tests
- Hypothesis framework
- Input validation
- Data consistency

## Future Enhancements

### Potential Improvements
1. Incremental updates (re-crawl changed pages)
2. Multi-language documentation support
3. Custom extraction rules per site
4. Caching layer for frequently accessed content
5. Webhook support for documentation updates
6. Vector search for semantic queries
7. Support for additional AI models
8. Distributed crawling for large sites

## Monitoring and Logging

### Logging Configuration
```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### Log Levels
- INFO: Pipeline progress, tool registration
- WARNING: Fallback usage, missing content
- ERROR: Network failures, AI errors, database issues
- DEBUG: Detailed execution traces

### Key Metrics
- Pages crawled successfully
- Content groups created
- Tools registered
- Tool invocation count
- Error rates by component

## Conclusion

Jedi-MCP provides a robust, AI-powered solution for transforming documentation websites into accessible MCP servers. Its modular architecture, comprehensive error handling, and flexible configuration make it suitable for a wide range of documentation sources and deployment scenarios.
