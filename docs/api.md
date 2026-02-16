# Core API Reference

Complete reference for the mcpstat Python API.

---

## MCPStat Class

The main class for usage tracking.

### Constructor

```python
from mcpstat import MCPStat

stat = MCPStat(
    server_name: str,
    *,
    db_path: str | None = None,
    log_path: str | None = None,
    log_enabled: bool | None = None,
    metadata_presets: dict[str, dict] | None = None,
    cleanup_orphans: bool = True,
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `server_name` | `str` | Required | Identifier for your MCP server |
| `db_path` | `str` | `./mcp_stat_data.sqlite` | SQLite database path |
| `log_path` | `str` | `./mcp_stat.log` | File log path |
| `log_enabled` | `bool` | `False` | Enable file logging |
| `metadata_presets` | `dict` | `None` | Pre-defined metadata |
| `cleanup_orphans` | `bool` | `True` | Remove metadata for unregistered tools on sync |

---

## Core Methods

### @stat.track (Recommended)

Decorator that automatically tracks tool calls with latency measurement.

```python
@app.call_tool()
@stat.track  # ← One decorator does everything!
async def handle_tool(name: str, arguments: dict):
    return await my_logic(arguments)
```

**Features:**

- Automatically measures execution time
- Records call count
- Tracks success/failure
- Never fails user code (errors suppressed)
- Works with exceptions (still records the call)

**With explicit type:**

```python
@stat.track(primitive_type="prompt")
async def handle_prompt(name: str, arguments: dict):
    return await generate_prompt(arguments)
```

---

### stat.tracking() Context Manager

For cases where you need more control than a decorator:

```python
async def handle_tool(name: str, arguments: dict):
    async with stat.tracking(name, "tool"):
        result = await my_logic(arguments)
        return result
```

---

### record()

Low-level method for manual recording. Use `@stat.track` instead when possible.

```python
await stat.record(
    name: str,
    primitive_type: Literal["tool", "prompt", "resource"] = "tool",
    *,
    success: bool = True,
    error_msg: str | None = None,
    response_chars: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    duration_ms: int | None = None,
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Name of the primitive |
| `primitive_type` | `str` | Type: `tool`, `prompt`, or `resource` |
| `success` | `bool` | Whether invocation succeeded |
| `error_msg` | `str` | Error message for failures (logged only) |
| `response_chars` | `int` | Response size for token estimation |
| `input_tokens` | `int` | Actual input token count |
| `output_tokens` | `int` | Actual output token count |
| `duration_ms` | `int` | Execution duration in milliseconds |

!!! note "When to use record()"
    Use `record()` directly only when you need to pass additional data like `response_chars` or `input_tokens`. For basic tracking with automatic latency, use `@stat.track` (decorator) or `stat.tracking()` (context manager) instead.

---

### get_stats()

Query usage statistics.

```python
stats = await stat.get_stats(
    *,
    include_zero: bool = True,
    limit: int | None = None,
    type_filter: Literal["tool", "prompt", "resource"] | None = None,
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `include_zero` | `bool` | Include items with zero calls |
| `limit` | `int` | Maximum results to return |
| `type_filter` | `str` | Filter by primitive type |

**Returns:**

```python
{
    "tracked_count": int,       # Total tracked items
    "total_calls": int,         # Sum of all call counts
    "zero_count": int,          # Items with zero calls
    "latest_access": str,       # Most recent timestamp
    "token_summary": {
        "total_input_tokens": int,
        "total_output_tokens": int,
        "total_estimated_tokens": int,
        "has_actual_tokens": bool,
    },
    "latency_summary": {
        "total_duration_ms": int,
        "has_latency_data": bool,
    },
    "stats": [
        {
            "name": str,
            "type": str,
            "call_count": int,
            "last_accessed": str | None,
            "tags": list[str],
            "short_description": str | None,
            "full_description": str | None,
            "total_input_tokens": int,
            "total_output_tokens": int,
            "total_response_chars": int,
            "estimated_tokens": int,
            "avg_tokens_per_call": int,
            "total_duration_ms": int,
            "min_duration_ms": int | None,
            "max_duration_ms": int | None,
            "avg_latency_ms": int,
        }
    ]
}
```

---

### get_catalog()

Browse and search the tool catalog.

```python
catalog = await stat.get_catalog(
    *,
    tags: list[str] | None = None,
    query: str | None = None,
    include_usage: bool = True,
    limit: int | None = None,
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `tags` | `list[str]` | Filter by tags (AND logic) |
| `query` | `str` | Text search across names/descriptions |
| `include_usage` | `bool` | Include call counts |
| `limit` | `int` | Maximum results |

!!! info "AND Logic"
    Tag filtering uses AND logic - tools must have **all** specified tags.

**Returns:**

```python
{
    "total_tracked": int,       # Total tools in catalog
    "matched": int,             # Tools matching filters
    "all_tags": list[str],      # Complete tag inventory
    "filters": {
        "tags": list[str],
        "query": str | None,
    },
    "include_usage": bool,
    "limit": int | None,
    "total_calls": int | None,   # None when include_usage=False
    "results": [
        {
            "name": str,
            "tags": list[str],
            "short_description": str | None,
            "full_description": str | None,
            "schema_version": int,
            "updated_at": str,
            "call_count": int | None,   # None when include_usage=False
            "last_accessed": str | None,
        }
    ]
}
```

---

### report_tokens()

Report token usage for a previously recorded call.

```python
await stat.report_tokens(
    name: str,
    input_tokens: int,
    output_tokens: int,
)
```

Use when actual token counts are available after the fact (e.g., from LLM API response).

**Example:**

```python
# Record the call first
await stat.record("my_tool", "tool")

# Later, when you have actual tokens
response = await anthropic.messages.create(...)
await stat.report_tokens(
    "my_tool",
    response.usage.input_tokens,
    response.usage.output_tokens
)
```

---

### sync_tools()

Sync metadata from MCP Tool objects.

```python
await stat.sync_tools(tools: list[Tool])
```

Auto-extracts tags from tool names and descriptions from tool definitions.

**Example:**

```python
tools = await server.list_tools()
await stat.sync_tools(tools)
```

---

### register_metadata()

Manually register metadata for a primitive.

```python
await stat.register_metadata(
    name: str,
    *,
    tags: list[str],
    short_description: str,
    full_description: str | None = None,
)
```

---

### sync_prompts()

Sync metadata from MCP Prompt objects.

```python
await stat.sync_prompts(prompts: list[Prompt])
```

---

### sync_resources()

Sync metadata from MCP Resource objects.

```python
await stat.sync_resources(resources: list[Resource])
```

---

### add_preset()

Add a metadata preset for future sync operations.

```python
stat.add_preset(
    name: str,
    *,
    tags: list[str],
    short: str,
)
```

---

### get_by_type()

Get usage statistics grouped by MCP primitive type.

```python
data = await stat.get_by_type()
```

**Returns:**

```python
{
    "by_type": {
        "tool": [{"name": str, "type": str, "call_count": int, "last_accessed": str}],
        "prompt": [...],
        "resource": [...],
    },
    "summary": {
        "tool": {"count": int, "total_calls": int},
        ...
    },
    "total_calls": int,
    "total_items": int,
}
```

---

### close()

Release resources. Call during server shutdown for clean resource release.

```python
stat.close()
```

---

## Built-in Tools

### build_tool_definitions()

Generate MCP tool schemas for mcpstat's built-in tools.

```python
from mcpstat import build_tool_definitions

tools = build_tool_definitions(
    prefix: str = "get",
    server_name: str = "MCP server",
)
```

Returns tool definitions for:

- `get_tool_usage_stats`
- `get_tool_catalog`

---

### BuiltinToolsHandler

Handle calls to mcpstat's built-in tools.

```python
from mcpstat import BuiltinToolsHandler

handler = BuiltinToolsHandler(stat, prefix="get")

# Check if a tool name is a stats tool
if handler.is_stats_tool(name):
    result = await handler.handle(name, arguments)
```

**Methods:**

| Method | Description |
|--------|-------------|
| `is_stats_tool(name)` | Check if name is a built-in stats tool |
| `handle(name, args)` | Handle the tool call, return result dict |

---

## Prompts

### build_prompt_definition()

Generate MCP prompt schema for stats prompt.

```python
from mcpstat import build_prompt_definition

prompt = build_prompt_definition(
    prompt_name: str,
    server_name: str = "MCP server",
)
```

---

### generate_stats_prompt()

Generate prompt content with current stats.

```python
from mcpstat import generate_stats_prompt

content = await generate_stats_prompt(
    stat,
    *,
    period: str = "all time",
    type_filter: str = "all",
    include_recommendations: bool = True,
)
```

---

### handle_stats_prompt()

Handle stats prompt request from MCP client.

```python
from mcpstat.prompts import handle_stats_prompt

result = await handle_stats_prompt(stat, arguments={"period": "past week"})
```

---

## Utility Functions

### normalize_tags()

Normalize and filter tags from text.

```python
from mcpstat.utils import normalize_tags

tags = normalize_tags(
    ["Fetch", "Weather", "Data", "the"],
    filter_stopwords=True
)
# ["fetch", "weather", "data"]
```
