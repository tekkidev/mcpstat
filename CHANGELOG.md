# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/tekkidev/mcpstat/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/tekkidev/mcpstat/releases/tag/v0.1.0
