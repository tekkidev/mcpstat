# Configuration

Configure mcpstat via constructor arguments or environment variables.

---

## Constructor Options

```python
from mcpstat import MCPStat

stat = MCPStat(
    "my-server",
    db_path="./stats.sqlite",      # SQLite database path
    log_path="./usage.log",        # File log path
    log_enabled=True,              # Enable file logging
    metadata_presets={             # Pre-define tool metadata
        "my_tool": {
            "tags": ["api", "data"],
            "short": "Fetch data from API"
        }
    },
)
```

---

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `server_name` | `str` | Required | Identifier for your MCP server |
| `db_path` | `str` | `./mcp_stat_data.sqlite` | Path to SQLite database |
| `log_path` | `str` | `./mcp_stat.log` | Path to file log |
| `log_enabled` | `bool` | `False` | Enable timestamped file logging |
| `metadata_presets` | `dict` | `{}` | Pre-defined metadata for tools |

---

## Environment Variables

Environment variables override constructor arguments:

| Variable | Description |
|----------|-------------|
| `MCPSTAT_DB_PATH` | SQLite database path |
| `MCPSTAT_LOG_PATH` | Log file path |
| `MCPSTAT_LOG_ENABLED` | Enable logging (`true`, `1`, `yes`) |

```bash
export MCPSTAT_DB_PATH=./stats.sqlite
export MCPSTAT_LOG_PATH=./usage.log
export MCPSTAT_LOG_ENABLED=true
```

---

## Metadata Presets

Pre-define tags and descriptions for tools:

```python
stat = MCPStat(
    "my-server",
    metadata_presets={
        "fetch_weather": {
            "tags": ["api", "weather", "external"],
            "short": "Fetch weather data from external API"
        },
        "parse_json": {
            "tags": ["utility", "parsing"],
            "short": "Parse JSON strings"
        },
    },
)
```

### Metadata Fields

| Field | Type | Description |
|-------|------|-------------|
| `tags` | `list[str]` | Categories for filtering |
| `short` | `str` | Brief description (one line) |
| `full` | `str` | Extended description (optional) |

---

## Auto-Tag Extraction

When syncing MCP tools, tags are auto-derived from tool names:

```python
# Sync metadata from your MCP server's tools
tools = await server.list_tools()
await stat.sync_tools(tools)
```

Auto-extraction rules:

- Names split on `-` and `_`
- Normalized to lowercase
- Stopwords filtered (`the`, `to`, `from`, `and`, etc.)

Example: `fetch_weather_data` → `["fetch", "weather", "data"]`

---

## Manual Metadata Registration

Register metadata at runtime:

```python
await stat.register_metadata(
    "my_tool",
    tags=["api", "weather", "external"],
    short_description="Fetch weather data from external API"
)
```

---

## File Logging

When enabled, mcpstat writes a timestamped log:

```
2026-02-01T10:30:45|tool:fetch_weather|OK
2026-02-01T10:30:46|tool:parse_json|OK
2026-02-01T10:30:47|prompt:weather_summary|OK
```

Useful for:

- Debugging agent behavior
- Detecting loops (repeated calls in short time)
- Audit trails

---

## Database Schema

mcpstat uses SQLite with two tables:

### `mcpstat_usage`

| Column | Type | Description |
|--------|------|-------------|
| `name` | TEXT | Primitive name (primary key) |
| `type` | TEXT | `tool`, `prompt`, or `resource` |
| `call_count` | INTEGER | Total invocations |
| `last_accessed` | TEXT | ISO 8601 timestamp |
| `total_input_tokens` | INTEGER | Cumulative input tokens |
| `total_output_tokens` | INTEGER | Cumulative output tokens |
| `estimated_tokens` | INTEGER | Estimated from response size |

### `mcpstat_metadata`

| Column | Type | Description |
|--------|------|-------------|
| `name` | TEXT | Primitive name (primary key) |
| `tags` | TEXT | Comma-separated tags |
| `short_description` | TEXT | Brief description |
| `full_description` | TEXT | Extended description |

---

## Best Practices

### 1. Single Instance

Create one `MCPStat` instance at module level:

```python
# ✅ Correct
stat = MCPStat("my-server")

async def handle_tool(name, args):
    await stat.record(name, "tool")
```

```python
# ❌ Wrong - creates new instance per call
async def handle_tool(name, args):
    stat = MCPStat("my-server")  # Don't do this
    await stat.record(name, "tool")
```

### 2. Record First

Always place `stat.record()` as the FIRST line:

```python
# ✅ Correct - always tracked
async def handle_tool(name, args):
    await stat.record(name, "tool")
    result = do_something(args)
    return result
```

```python
# ❌ Wrong - if do_something crashes, call isn't tracked
async def handle_tool(name, args):
    result = do_something(args)
    await stat.record(name, "tool")
    return result
```

### 3. Use Environment Variables in Production

```bash
# docker-compose.yml
services:
  mcp-server:
    environment:
      - MCPSTAT_DB_PATH=/data/stats.sqlite
      - MCPSTAT_LOG_ENABLED=true
```
