# mcpstat

[![PyPI - Version](https://img.shields.io/pypi/v/mcpstat)](https://pypi.org/project/mcpstat/)
[![GitHub License](https://img.shields.io/github/license/tekkidev/mcpstat?color=yellow)](https://github.com/tekkidev/mcpstat/blob/main/LICENSE)
[![PyPI - Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://pypi.org/project/mcpstat/)

**mcpstat** adds usage tracking and analytics to your [MCP (Model Context Protocol)](https://modelcontextprotocol.io) servers. Pure Python stdlib, no required dependencies.

Track which tools get called, how often, and keep an audit trail - all in about three lines of code. Then ask your AI assistant: *"Give me MCP usage stats."*

---

## Why mcpstat?

MCP is becoming the standard integration layer between AI assistants and external tools. Adding observability to this layer provides concrete benefits:

| Benefit | Description |
|---------|-------------|
| **Identify active vs. inactive tools** | Understand which tools deliver value and which can be removed or improved. |
| **Optimize context usage** | Track whether resources provide useful context or consume tokens without benefit. |
| **Detect usage patterns** | Spot agent loops, repeated calls, or unexpected tool combinations. |
| **Measure MCP adoption** | Quantify how often your LLM actually uses MCP integrations. |

Without tracking, agents may pull irrelevant resources into context - leading to token waste or lower-quality responses. mcpstat provides the visibility to identify and address these issues.

---

## Features

- **SQLite-backed tracking** - Stats persist across restarts
- **Optional file logging** - Timestamped audit trail for debugging
- **Built-in tools & prompts** - Expose stats directly to LLM clients
- **Metadata enrichment** - Tag and describe tools for discoverability
- **Token tracking** - Estimate or record actual token usage
- **Async-first** - Thread-safe via `asyncio.Lock`

---

## Quick Start

### Installation

```bash
pip install mcpstat
```

For MCP SDK integration:

```bash
pip install "mcpstat[mcp]"
```

### Minimal Integration

```python
from mcp.server import Server
from mcpstat import MCPStat

app = Server("my-server")
stat = MCPStat("my-server")  # Initialize

@app.call_tool()
async def handle_tool(name: str, arguments: dict):
    await stat.record(name, "tool")  # Track as FIRST line
    # ... your tool logic
```

One line - `await stat.record(name, "tool")` - and you're tracking.

---

## Built-in Tools

mcpstat exposes two tools that AI assistants can call directly:

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

| Guide | Description |
|-------|-------------|
| [Quick Start](quickstart.md) | Install mcpstat and add tracking to your first MCP server in minutes. |
| [Configuration](configuration.md) | Configure paths, logging, metadata presets, and environment variables. |
| [API Reference](api.md) | Complete reference for `MCPStat`, built-in tools, and handlers. |
| [Token Tracking](token-tracking.md) | Track response sizes and estimate token usage for cost analysis. |

---

## Links

- **PyPI**: [pypi.org/project/mcpstat](https://pypi.org/project/mcpstat/)
- **GitHub**: [github.com/tekkidev/mcpstat](https://github.com/tekkidev/mcpstat)
- **MCP Protocol**: [modelcontextprotocol.io](https://modelcontextprotocol.io)

---

## License

MIT - see [LICENSE](https://github.com/tekkidev/mcpstat/blob/main/LICENSE)
