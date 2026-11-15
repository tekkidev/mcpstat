# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-11-15

### Added

- Bundled documentation and demo MCP server, `mcpstat` CLI, SDK v2 integration, and registry manifest.
- Persistent success, error, cancellation, and incomplete counters; explicit names for tracked handlers.
- Agent documentation index, full reference, and Markdown alternatives.

### Changed

- Nonblocking SQLite operations, isolated server/primitive identities, and catalog synchronization
  that preserves history and includes unused registrations.
- Rotating JSON Lines logs that omit exception messages; stricter analytics input validation.
- Inbound SDK tracing disabled in the bundled server and examples; `disable_sdk_tracing()`
  provides the same control for existing SDK v2 servers.

### Migration

- Back up databases before the automatic, one-way migration. Keep the server name stable;
  restore the backup to downgrade.
- The SDK extras require MCP SDK >=2.3,<3; SDK v1 integrations need handler updates.
  The core remains SDK-independent.
- Update log parsers for JSON Lines. Explicit query limits must be 1-1000; periods accept
  only `all time`. Historical latency averages with unknown sample counts are `None`.

See the [upgrade guide](docs/configuration.md#upgrading-from-02x) for compatibility details.

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

[0.3.0]: https://github.com/tekkidev/mcpstat/compare/v0.2.2...v0.3.0
[0.2.2]: https://github.com/tekkidev/mcpstat/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/tekkidev/mcpstat/compare/v0.1.2...v0.2.1
[0.1.2]: https://github.com/tekkidev/mcpstat/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/tekkidev/mcpstat/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/tekkidev/mcpstat/releases/tag/v0.1.0
