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
    db_path: str | None = None,
    log_path: str | None = None,
    log_enabled: bool = False,
    metadata_presets: dict[str, dict] | None = None,
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `server_name` | `str` | Required | Identifier for your MCP server |
| `db_path` | `str` | `./mcp_stat_data.sqlite` | SQLite database path |
| `log_path` | `str` | `./mcp_stat.log` | File log path |
| `log_enabled` | `bool` | `False` | Enable file logging |
| `metadata_presets` | `dict` | `None` | Pre-defined metadata |

---

## Core Methods

### record()

Record a tool, prompt, or resource invocation.

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

> **Critical**: Always call `record()` as the **FIRST line** in your handlers to guarantee 100% tracking coverage.

**Example:**

```python
@app.call_tool()
async def handle_tool(name: str, arguments: dict):
    await stat.record(name, "tool")  # FIRST LINE
    result = await my_logic(arguments)
    return result
```

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
    "stats": [
        {
            "name": str,
            "type": str,
            "call_count": int,
            "last_accessed": str | None,
            "tags": list[str],
            "short_description": str | None,
            "total_input_tokens": int,
            "total_output_tokens": int,
            "estimated_tokens": int,
            "avg_tokens_per_call": int,
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

> **AND Logic**: Tag filtering uses AND logic - tools must have **all** specified tags.

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
    "results": [
        {
            "name": str,
            "tags": list[str],
            "short_description": str | None,
            "call_count": int,
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

Manually register metadata for a tool.

```python
await stat.register_metadata(
    name: str,
    tags: list[str] | None = None,
    short_description: str | None = None,
    full_description: str | None = None,
)
```

---

### get_by_type()

Get call counts grouped by type.

```python
counts = await stat.get_by_type()
# {"tool": 15, "prompt": 3, "resource": 2}
```

---

### close()

Explicit cleanup (usually automatic).

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
    server_name: str | None = None,
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

prompt = build_prompt_definition(server_name="my-server")
```

---

### generate_stats_prompt()

Generate prompt content with current stats.

```python
from mcpstat import generate_stats_prompt

content = await generate_stats_prompt(stat, server_name="my-server")
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
