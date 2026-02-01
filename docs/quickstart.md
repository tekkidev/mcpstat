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

Add usage tracking to any MCP server with three lines of code:

```python
from mcp.server import Server
from mcpstat import MCPStat

app = Server("my-server")
stat = MCPStat("my-server")  # Initialize - creates SQLite database automatically

@app.call_tool()
async def handle_tool(name: str, arguments: dict):
    await stat.record(name, "tool")  # Track as FIRST line for 100% coverage
    # ... your tool logic
```

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
    your_tools = [
        {"name": "my_tool", "description": "...", "inputSchema": {...}},
    ]
    stats_tools = build_tool_definitions(server_name="my-server")
    return your_tools + stats_tools

# Handle tool calls
@app.call_tool()
async def handle_tool(name: str, arguments: dict):
    await stat.record(name, "tool")  # Always FIRST

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
@app.get_prompt()
async def get_prompt(name: str, arguments: dict):
    await stat.record(name, "prompt")  # Track prompts
    # ... your prompt logic

@app.read_resource()
async def read_resource(uri: str):
    await stat.record(uri, "resource")  # Track resources
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
  "stats": [
    {
      "name": "fetch_weather",
      "type": "tool",
      "call_count": 15,
      "last_accessed": "2026-02-01T10:30:45+00:00",
      "tags": ["api", "weather"],
      "short_description": "Fetch weather data"
    }
  ]
}
```

---

## Next Steps

- [Configuration](configuration.md) - Customize paths, logging, and presets
- [Core API](api.md) - Complete API reference
- [Token Tracking](token-tracking.md) - Track token usage for cost analysis
