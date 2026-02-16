# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.2] - 2026-02-16

### Added

- **Latency Tracking**: Track execution duration for each tool call
  - `@stat.track` decorator for automatic latency tracking (recommended)
  - `async with stat.tracking(name, type)` context manager alternative
  - `duration_ms` parameter in `record()` for manual timing
  - New latency columns: `total_duration_ms`, `min_duration_ms`, `max_duration_ms`
  - `latency_summary` in `get_stats()` response with total duration
  - Per-tool `avg_latency_ms`, `min_duration_ms`, `max_duration_ms` metrics

### Changed

- Database schema bumped to v3 with latency tracking columns
- `get_stats()` response now includes `latency_summary` object
- Each stat item now includes latency fields
- **API Improvement**: `@stat.track` decorator is now the recommended way to track calls
  - Eliminates the "first line" requirement
  - Automatic latency measurement
  - Never fails user code

### Migration

- Automatic database migration from v2 to v3
- Preserves all existing data
- New latency columns default to 0/NULL for existing records

## [0.2.1] - 2026-02-01

### Added

- **Token Tracking**: New feature to track response sizes and estimate token usage
  - `response_chars` parameter in `record()` for automatic token estimation
  - `input_tokens` and `output_tokens` parameters for actual token tracking
  - New `report_tokens()` method for deferred token reporting
  - Token summary in `get_stats()` response with totals and averages
- **Schema Migration**: Automatic database migration from v1 to v2
  - Adds token tracking columns with backward compatibility
  - Preserves all existing data
- **Documentation**: Added new and updated guides, API references, and examples

### Changed

- Database schema bumped to v2 with new columns:
  - `total_input_tokens`, `total_output_tokens`
  - `total_response_chars`, `estimated_tokens`
- `get_stats()` response now includes `token_summary` object
- Each stat item now includes token fields and `avg_tokens_per_call`

## [0.1.2] - 2026-01-17

### Added

- GitHub community files: CONTRIBUTING.md, SECURITY.md, issue/PR templates
- Tags System documentation with filtering examples
- Expanded API Reference with complete code examples
- Test coverage improved

### Changed

- Improved README.md structure and navigation with collapsible MCP client configs
- Enhanced llms.txt for better AI agent consumption

## [0.1.1] - 2026-01-16

### Fixed

- Python 3.10 compatibility: replaced `datetime.UTC` with `datetime.timezone.utc`

## [0.1.0] - 2026-01-16

### Added

- **Core**: `MCPStat` class - unified API for usage tracking and analytics
- **Database**: `MCPStatDatabase` - SQLite-backed storage with async-safe operations
- **Logging**: `MCPStatLogger` - optional file-based audit logging (pipe-delimited format)
- **Built-in tools** for exposing stats to MCP clients:
  - `get_tool_usage_stats`: Query tool usage statistics with filtering
  - `get_tool_catalog`: Browse registered tools with tags, search, and metadata
- **Prompts**: `generate_stats_prompt()` for LLM-friendly usage reports
- **Helpers**: `build_tool_definitions()` and `build_prompt_definition()` for easy MCP registration
- **Handler**: `BuiltinToolsHandler` class for handling built-in tool calls
- **Utils**: `normalize_tags()` with stopword filtering, `derive_short_description()` utilities
- Metadata enrichment system with tags and descriptions
- `sync_tools()`, `sync_prompts()`, `sync_resources()` for automatic metadata sync from MCP objects
- `type_filter` parameter in `get_tool_usage_stats` for filtering by primitive type
- Environment variable configuration support (`MCPSTAT_DB_PATH`, `MCPSTAT_LOG_PATH`, `MCPSTAT_LOG_ENABLED`)
- Async-first design with thread-safe internals
- No required dependencies (pure Python stdlib)
- Optional `mcp` extra for MCP SDK integration
- Full type annotations with strict mypy compliance (`py.typed` marker included)
- Comprehensive test suite

[Unreleased]: https://github.com/tekkidev/mcpstat/compare/v0.2.2...HEAD
[0.2.2]: https://github.com/tekkidev/mcpstat/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/tekkidev/mcpstat/compare/v0.1.2...v0.2.1
[0.1.2]: https://github.com/tekkidev/mcpstat/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/tekkidev/mcpstat/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/tekkidev/mcpstat/releases/tag/v0.1.0
