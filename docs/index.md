# mcpstat

[![PyPI - Version](https://img.shields.io/pypi/v/mcpstat)](https://pypi.org/project/mcpstat/)
[![GitHub License](https://img.shields.io/github/license/tekkidev/mcpstat?color=yellow)](https://github.com/tekkidev/mcpstat/blob/main/LICENSE)
[![PyPI - Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://pypi.org/project/mcpstat/)

**mcpstat** is a Python observability and usage analytics library for [MCP (Model Context Protocol)](https://modelcontextprotocol.io) servers.

Track tool, prompt, and resource calls, successful and failed invocations, and execution
latency in local SQLite storage. Instrument your existing server and register its
analytics tools, then ask your AI assistant: *"Give me MCP usage stats."* Optional file
logging provides an audit trail. The core library is SDK-independent; the bundled
documentation and demonstration server tracks its own activity.

Follow the [weather server walkthrough](quickstart.md#verify-mcp-tool-usage-with-a-weather-server)
to send real MCP requests, inspect the resulting counters, and verify restart persistence.

[mcpstat for Visual Studio Code](https://github.com/tekkidev/mcpstat-vscode) displays
calls, errors, latency and handler usage. Your server records the statistics.
The extension reads them through VS Code's MCP tools, an HTTP endpoint, or directly
from a SQLite database.

---

## Why mcpstat?

Usage statistics help you review which handlers run, how often they fail, and how
long measured calls take.

| Benefit | Description |
|---------|-------------|
| **Identify active vs. inactive tools** | Compare recorded calls and find registered handlers with no recorded use. |
| **Review token usage** | Compare reported token counts and estimates separately. |
| **Investigate repeated calls** | Compare handler counts and use optional file logs to investigate individual calls. |
| **Measure MCP usage** | Count invocations of the handlers you instrument across their clients. |

Counts show frequency. They do not measure response quality or explain why an agent
chose a tool.

---

## Features

- **SQLite-backed tracking** - Stats persist across restarts
- **Optional file logging** - Timestamped audit trail for debugging
- **Built-in tools & prompts** - Expose stats directly to LLM clients
- **Metadata enrichment** - Tag and describe tools for discoverability
- **Token tracking** - Estimate or record actual token usage
- **Latency tracking** - Measure execution time, identify slow tools
- **Async-first** - Database operations run in worker threads with serialized transactions

---

## Quick Start

### Installation

```bash
pip install "mcpstat[server]"
```

### Minimal Integration

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

The decorator records each invocation and its duration. Register statistics tools
to query the results.

---

## Built-in Tools

mcpstat provides definitions and handlers for two analytics tools. Register them in your
server as shown in the [full integration pattern](quickstart.md#full-integration-pattern):

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `get_tool_usage_stats` | Call counts & timestamps | `type_filter`, `limit`, `include_zero_usage` |
| `get_tool_catalog` | Browse & search tools | `tags`, `query`, `include_usage`, `limit` |

### Natural Language Queries

Users can ask AI assistants:

- *"Give me MCP usage stats"*
- *"Which tools are used most often?"*
- *"List tools tagged with 'temperature'"*

The AI invokes `get_tool_usage_stats` or `get_tool_catalog` as needed.

---

## Documentation

[Agent documentation index](https://mcpstat.vadim.dev/llms.txt) and
[full agent reference](https://mcpstat.vadim.dev/llms-full.txt) provide plain-text entry
points. The documentation website also links each page to its Markdown source.

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **Getting Started**

    ---

    Install mcpstat and add tracking to a Python MCP server.

    [:octicons-arrow-right-24: Quick Start](quickstart.md)

-   :material-cog:{ .lg .middle } **Configuration**

    ---

    Configure paths, logging, metadata presets, and environment variables.

    [:octicons-arrow-right-24: Configuration](configuration.md)

-   :material-api:{ .lg .middle } **Core API**

    ---

    Complete reference for `MCPStat`, built-in tools, and handlers.

    [:octicons-arrow-right-24: API Reference](api.md)

-   :material-chart-line:{ .lg .middle } **Token Tracking**

    ---

    Track response sizes and estimate token usage for cost analysis.

    [:octicons-arrow-right-24: Token Tracking](token-tracking.md)

-   :material-timer-outline:{ .lg .middle } **Latency Tracking**

    ---

    Measure tool execution time to identify slow tools and monitor performance.

    [:octicons-arrow-right-24: Latency Tracking](latency-tracking.md)

</div>

---

## Links

- **PyPI**: [pypi.org/project/mcpstat](https://pypi.org/project/mcpstat/)
- **GitHub**: [github.com/tekkidev/mcpstat](https://github.com/tekkidev/mcpstat)
- **MCP Protocol**: [modelcontextprotocol.io](https://modelcontextprotocol.io)

---

## License

MIT - see [LICENSE](https://github.com/tekkidev/mcpstat/blob/main/LICENSE)
