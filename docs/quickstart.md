# Quick Start

Get mcpstat running in your MCP server in under five minutes.

---

## Installation

```bash
pip install mcpstat
```

For MCP SDK integration:

```bash
pip install "mcpstat[mcp]"
```

---

## Minimal Integration

Add usage tracking to any MCP server with one decorator:

```python
from mcp.server import Server
from mcpstat import MCPStat

app = Server("my-server")
stat = MCPStat("my-server")  # Creates SQLite database automatically

@app.call_tool()
@stat.track  # ← One decorator does everything!
async def handle_tool(name: str, arguments: dict):
    return await my_logic(arguments)  # Latency tracked automatically
```

That's it! The `@stat.track` decorator automatically:

- Records every call
- Measures execution time (latency)
- Tracks success/failure
- Never crashes your code (errors are suppressed)

---

## Full Integration Pattern

For production servers with built-in stats tools:

```python
import json
from mcp.server import Server
from mcp.types import TextContent
from mcpstat import (
    MCPStat,
    build_tool_definitions,
    BuiltinToolsHandler,
)

# Initialize
app = Server("my-server")
stat = MCPStat(
    "my-server",
    db_path="./stats.sqlite",
    log_enabled=True,
    metadata_presets={
        "my_tool": {"tags": ["api"], "short": "Fetch data"}
    },
)
handler = BuiltinToolsHandler(stat)

# List your tools + mcpstat's built-in tools
@app.list_tools()
async def list_tools():
    from mcp.types import Tool

    your_tools = [
        Tool(
            name="my_tool",
            description="Does something useful",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]
    stats_tools = [
        Tool(name=t["name"], description=t["description"], inputSchema=t["inputSchema"])
        for t in build_tool_definitions(server_name="my-server")
    ]
    all_tools = your_tools + stats_tools
    await stat.sync_tools(all_tools)
    return all_tools

# Handle tool calls with automatic latency tracking
@app.call_tool()
@stat.track
async def handle_tool(name: str, arguments: dict):

    # Handle mcpstat's built-in tools
    if handler.is_stats_tool(name):
        result = await handler.handle(name, arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # Handle your tools
    if name == "my_tool":
        return [TextContent(type="text", text="Your result")]

    raise ValueError(f"Unknown tool: {name}")
```

---

## Track Prompts and Resources

mcpstat tracks any MCP primitive:

```python
# Prompts - use @stat.track with explicit type
@app.get_prompt()
@stat.track(primitive_type="prompt")
async def get_prompt(name: str, arguments: dict | None = None):
    # ... your prompt logic

# Resources - use tracking() context manager
@app.read_resource()
async def read_resource(uri: str):
    uri_str = str(uri)  # MCP SDK may pass AnyUrl
    resource_name = uri_str.split("/")[-1] if "/" in uri_str else uri_str
    async with stat.tracking(resource_name, "resource"):
        # ... your resource logic
```

---

## Query Your Stats

### Via AI Assistant

Just ask:

- *"Give me MCP usage stats"*
- *"Which tools are most used?"*
- *"Find all API-related tools"*

### Programmatically

```python
# Get all stats
stats = await stat.get_stats()

# Filter by type
stats = await stat.get_stats(type_filter="tool", include_zero=False)

# Browse catalog with tags
catalog = await stat.get_catalog(tags=["api", "weather"])

# Text search
catalog = await stat.get_catalog(query="temperature")
```

---

## Example Response

```json
{
  "tracked_count": 5,
  "total_calls": 42,
  "zero_count": 2,
  "latest_access": "2026-02-01T10:30:45+00:00",
  "token_summary": {
    "total_input_tokens": 5000,
    "total_output_tokens": 12000,
    "total_estimated_tokens": 3500,
    "has_actual_tokens": true
  },
  "latency_summary": {
    "total_duration_ms": 15000,
    "has_latency_data": true
  },
  "stats": [
    {
      "name": "fetch_weather",
      "type": "tool",
      "call_count": 15,
      "last_accessed": "2026-02-01T10:30:45+00:00",
      "tags": ["api", "weather"],
      "short_description": "Fetch weather data",
      "total_input_tokens": 1000,
      "total_output_tokens": 2500,
      "total_response_chars": 8000,
      "estimated_tokens": 2286,
      "avg_tokens_per_call": 233,
      "total_duration_ms": 5000,
      "min_duration_ms": 100,
      "max_duration_ms": 1200,
      "avg_latency_ms": 333
    }
  ]
}
```

---

## Next Steps

- [Configuration](configuration.md) - Customize paths, logging, and presets
- [Core API](api.md) - Complete API reference
- [Token Tracking](token-tracking.md) - Track token usage for cost analysis
- [Latency Tracking](latency-tracking.md) - Monitor tool execution time
