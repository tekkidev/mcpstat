# mcpstat

[![PyPI - Version](https://img.shields.io/pypi/v/mcpstat)](https://pypi.org/project/mcpstat/)
[![GitHub License](https://img.shields.io/github/license/tekkidev/mcpstat?color=yellow)](https://github.com/tekkidev/mcpstat/blob/main/LICENSE)
[![PyPI - Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://pypi.org/project/mcpstat/)
[![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/tekkidev/mcpstat/tests.yaml)](https://github.com/tekkidev/mcpstat/actions/workflows/tests.yaml)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/mcpstat)](https://pypistats.org/packages/mcpstat)
[![Codecov](https://codecov.io/gh/tekkidev/mcpstat/branch/main/graph/badge.svg)](https://codecov.io/gh/tekkidev/mcpstat)

**Usage tracking and analytics for MCP servers.** Pure Python, zero required dependencies.

Track which tools get called, how often, and keep an audit trail - all in 3 lines of code.

## Installation

```bash
pip install mcpstat
```

With MCP SDK:
```bash
pip install "mcpstat[mcp]"
```

## Quick Start

```python
from mcp.server import Server
from mcpstat import MCPStat

app = Server("my-server")
stat = MCPStat("my-server")

@app.call_tool()
async def handle_tool(name: str, arguments: dict):
    await stat.record(name, "tool")  # ← Add as FIRST line
    # ... your tool logic
```

Then ask your AI assistant: *"Give me MCP usage stats"*

## Features

- **SQLite-backed** - Stats persist across restarts
- **Built-in MCP tools** - `get_tool_usage_stats`, `get_tool_catalog`
- **Tag system** - Categorize and filter tools
- **Token tracking** - Estimate or record actual token usage
- **File logging** - Optional timestamped audit trail
- **Async-first** - Thread-safe via `asyncio.Lock`

## Documentation

**[Full Documentation](https://github.com/tekkidev/mcpstat/tree/main/docs)** - Quick start, API reference, examples

- [Quick Start](https://github.com/tekkidev/mcpstat/blob/main/docs/quickstart.md) - Get running in 5 minutes
- [Configuration](https://github.com/tekkidev/mcpstat/blob/main/docs/configuration.md) - Customize paths, logging, presets
- [API Reference](https://github.com/tekkidev/mcpstat/blob/main/docs/api.md) - Complete method reference
- [Token Tracking](https://github.com/tekkidev/mcpstat/blob/main/docs/token-tracking.md) - Cost analysis features

## Examples

```bash
# Clone and run example server
git clone https://github.com/tekkidev/mcpstat.git
cd mcpstat
pip install -e ".[mcp]"
python examples/example_server.py
```

See [examples/](https://github.com/tekkidev/mcpstat/tree/main/examples/) for minimal and full integration patterns.

## Contributing

See [CONTRIBUTING.md](https://github.com/tekkidev/mcpstat/blob/main/CONTRIBUTING.md). Run tests with:

```bash
pip install "mcpstat[dev]"
pytest tests/
```

## License

MIT - see [LICENSE](https://github.com/tekkidev/mcpstat/blob/main/LICENSE) for details.

---

*MCP is a trademark of its respective owners. This project is not affiliated with or endorsed by any trademark holders.*
