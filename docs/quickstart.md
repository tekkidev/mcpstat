# Quick Start

Get mcpstat running in your MCP server in under five minutes.

---

## Installation

```bash
pip install "mcpstat[server]"
```

---

## Minimal Integration

Add usage tracking to any MCP server with one decorator:

```python
from mcp.server import MCPServer
from mcpstat import MCPStat, disable_sdk_tracing

app = MCPServer("my-server")
disable_sdk_tracing(app)
stat = MCPStat("my-server")


@app.tool()
@stat.track(name="echo")
async def echo(message: str) -> str:
    """Return a message, measuring usage and execution time."""
    return message
```

That's it! The `@stat.track` decorator automatically:

- Records each wrapped invocation
- Measures execution time (latency)
- Tracks success/failure
- Suppresses tracking failures while preserving handler exceptions and cancellation

---

## Verify MCP Tool Usage with a Weather Server

The [weather server example](https://github.com/tekkidev/mcpstat/blob/main/examples/weather_server.py)
adds mcpstat to an independent Python MCP server. It returns synthetic weather data
without an API key or network request and exposes `get_tool_usage_stats` alongside its
business tools. It does not launch `mcpstat.server`.

### Install and send requests

Run these commands from a new checkout:

```bash
git clone https://github.com/tekkidev/mcpstat.git
cd mcpstat
python -m venv .venv
```

Activate the environment with `source .venv/bin/activate` on macOS or Linux, or
`.venv\Scripts\Activate.ps1` in Windows PowerShell. Then run:

```bash
python -m pip install ".[server]"
python examples/check_weather.py
```

The [client example](https://github.com/tekkidev/mcpstat/blob/main/examples/check_weather.py)
launches the weather server as a stdio subprocess, lists its tools, and queries a zero-use
baseline. It calls `get_weather` for London and Paris, calls `fail_tool` once, and retrieves
statistics through MCP. Each run uses fresh temporary databases and checks both modern
and handshake-based clients.

### Inspect the statistics

Each weather response contains the requested city, `temperature_c: 21.0`, and
`condition: "synthetic sunshine"`. `fail_tool` returns an MCP tool error with
`Intentional weather example failure`; this deliberately demonstrates error accounting.

The client prints these selected statistics for each protocol mode:

| Tool | `call_count` | `success_count` | `error_count` | `duration_sample_count` |
|------|--------------|-----------------|---------------|-------------------------|
| `get_weather` | 2 | 2 | 0 | 2 |
| `fail_tool` | 1 | 0 | 1 | 1 |
| `unused_tool` | 0 | 0 | 0 | 0 |

It then stops and restarts the server with the same database and queries statistics
again. The counters must persist. Duration measurements can be zero milliseconds for
these fast synthetic tools; `duration_sample_count` confirms that timing was recorded.

### Query from an assistant

Configure your MCP client to launch `examples/weather_server.py` with the Python
interpreter from the environment above. Use the script's absolute path if the client
starts processes in a different working directory. Running it in a terminal alone waits
for stdio protocol requests; it does not display a dashboard.

Send this to your connected assistant:

> Use only the weather MCP server. Call get_tool_usage_stats with {} for a baseline.
> Call get_weather with {"city":"London"}, then {"city":"Paris"}. Call fail_tool with {}
> exactly once; its failure is intentional. Retrieve statistics again and show the
> differences. Expect get_weather to gain two successful calls and two duration samples,
> and fail_tool to gain one call and one error. Do not call unused_tool. Use actual MCP
> tool results.

Manual sessions use `./weather_stats.sqlite` relative to the server's working directory,
unless `MCPSTAT_DB_PATH` overrides it. Compare deltas when a database already contains
usage. The example leaves its statistics tool untracked, so reading statistics does not
increment that tool's count. Add `@stat.track(name="get_tool_usage_stats")` below
`@app.tool()` to count queries too; a query's own completion appears in the next snapshot.

---

## Full Integration Pattern

For production servers with built-in stats tools:

```python
import asyncio
import json
import mcp_types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp_types import TextContent
from mcpstat import (
    MCPStat,
    build_tool_definitions,
    BuiltinToolsHandler,
    disable_sdk_tracing,
)

# Initialize
stat = MCPStat(
    "my-server",
    db_path="./stats.sqlite",
    log_enabled=True,
    metadata_presets={"my_tool": {"tags": ["api"], "short": "Fetch data"}},
)
handler = BuiltinToolsHandler(stat)

# List your tools + mcpstat's built-in tools


async def list_tools():
    from mcp_types import Tool

    your_tools = [
        Tool(
            name="my_tool",
            description="Does something useful",
            input_schema={"type": "object", "properties": {}},
        ),
    ]
    stats_tools = [
        Tool(name=t["name"], description=t["description"], input_schema=t["inputSchema"])
        for t in build_tool_definitions(server_name="my-server")
    ]
    all_tools = your_tools + stats_tools
    await stat.sync_tools(all_tools)
    return all_tools


# Handle tool calls with automatic latency tracking


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


# Adapt the dispatch handlers to the SDK's request/result models.
async def on_list_tools(ctx, params):
    return types.ListToolsResult(tools=await list_tools())


async def on_call_tool(ctx, params):
    try:
        return types.CallToolResult(content=await handle_tool(params.name, params.arguments or {}))
    except (ValueError, TypeError, KeyError):
        return types.CallToolResult(
            content=[TextContent(type="text", text="Invalid tool request")], is_error=True
        )


app = Server("my-server", on_list_tools=on_list_tools, on_call_tool=on_call_tool)
disable_sdk_tracing(app)


async def main():
    try:
        async with stdio_server() as (read, write):
            await app.run(read, write, app.create_initialization_options())
    finally:
        stat.close()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Track Prompts and Resources

mcpstat tracks any MCP primitive:

```python
# Prompts - use @stat.track with explicit type


@stat.track(primitive_type="prompt")
async def get_prompt(name: str, arguments: dict | None = None):
    return await generate_prompt(name, arguments)


# Resources - use tracking() context manager


async def read_resource(uri: str):
    uri_str = str(uri)  # MCP SDK may pass AnyUrl
    resource_name = uri_str
    async with stat.tracking(resource_name, "resource"):
        return await load_resource(uri_str)
```

---

## Query Your Stats

### Via AI Assistant

Register the analytics tools as shown above, then connect your assistant to that server.

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

## Standalone documentation server

Run `mcpstat` after installing `mcpstat[server]` to serve the packaged documentation,
temperature conversion tools, statistics, catalog, and usage prompt over stdio. It tracks
its own invocations. To track another server, add the library to that server's handlers.

For hosts using an MCP configuration file:

```json
{"mcpServers":{"mcpstat":{"command":"uvx","args":["--from","mcpstat[server]","mcpstat"],"env":{"OTEL_SDK_DISABLED":"true","OTEL_PROPAGATORS":"none"}}}}
```

The server uses MCP SDK >=2.3,<3 and accepts modern and handshake-based clients. Keep
protocol stdout separate from diagnostics on stderr. The core library can be installed
with `pip install mcpstat` when the bundled SDK integration is not needed.
