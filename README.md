# mcpstat

[![PyPI - Version](https://img.shields.io/pypi/v/mcpstat)](https://pypi.org/project/mcpstat/)
[![GitHub License](https://img.shields.io/github/license/tekkidev/mcpstat?color=yellow)](https://github.com/tekkidev/mcpstat/blob/main/LICENSE)
[![PyPI - Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://pypi.org/project/mcpstat/)
[![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/tekkidev/mcpstat/tests.yaml)](https://github.com/tekkidev/mcpstat/actions/workflows/tests.yaml)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/mcpstat)](https://pypistats.org/packages/mcpstat)
[![Checked with mypy](https://img.shields.io/badge/mypy-checked-blue)](http://mypy-lang.org/)
[![Security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)
[![Codecov](https://codecov.io/gh/tekkidev/mcpstat/branch/main/graph/badge.svg)](https://codecov.io/gh/tekkidev/mcpstat)

**Python observability and usage analytics for MCP (Model Context Protocol) servers.**

Track tool, prompt, and resource calls, successful and failed invocations, and execution
latency in local SQLite storage. Add tracking to your existing Python MCP server and
expose its statistics as MCP tools that an assistant can query. Optional file logging
provides an audit trail.

## Installation

```bash
pip install mcpstat
pip install "mcpstat[server]"  # Includes the SDK for the example below
```

## Quick Start

```python
from mcp.server import MCPServer
from mcpstat import MCPStat, disable_sdk_tracing

app = MCPServer("my-server")
disable_sdk_tracing(app)
stat = MCPStat("my-server")


@app.tool()
@stat.track(name="echo")
async def echo(message: str) -> str:
    """Return a message, tracking usage and latency automatically."""
    return message


@app.tool()
async def get_tool_usage_stats() -> dict:
    """Return cumulative MCP usage statistics."""
    return await stat.get_stats()


if __name__ == "__main__":
    try:
        app.run()
    finally:
        stat.close()
```

Connect your assistant to this server, then ask: *"Give me MCP usage stats"*

For a complete request-to-statistics example, follow the
[weather server walkthrough](https://github.com/tekkidev/mcpstat/blob/main/docs/quickstart.md#verify-mcp-tool-usage-with-a-weather-server).
It demonstrates successful calls, an intentional failure, unused tools, and statistics
that persist after restarting the server.

## Choose Your Integration

| Use case | Installation | What it tracks |
|----------|--------------|----------------|
| Add tracking to an existing Python server | `pip install mcpstat` | The handlers you instrument with the SDK-independent library; keep your server's MCP SDK installed separately. |
| Run the bundled documentation and demonstration server | `pip install "mcpstat[server]"` | Its own temperature conversion tools and other registered handlers. |

The decorator records usage; register a statistics tool such as `get_tool_usage_stats`
to query that data from Claude Code, VS Code, or another MCP client. The standalone
server does not automatically observe other MCP servers.

## Features

- **SQLite-backed** - Stats persist across restarts
- **Built-in MCP tools** - `get_tool_usage_stats`, `get_tool_catalog`
- **Tag system** - Categorize and filter tools
- **Token tracking** - Estimate or record actual token usage
- **Latency tracking** - Measure execution duration, identify slow tools
- **File logging** - Optional timestamped audit trail
- **Async-first** - Database operations run in worker threads with serialized transactions

Install `mcpstat` for the SDK-independent tracking library. The `[server]` extra includes
the SDK and the runnable `mcpstat` documentation and demonstration server. The standalone
server tracks its own calls; integrate the library into each server you want to monitor.

## Documentation

**[Full Documentation](https://github.com/tekkidev/mcpstat/tree/main/docs)** - Quick start, API reference, examples

- [Quick Start](https://github.com/tekkidev/mcpstat/blob/main/docs/quickstart.md) - Get running in 5 minutes
- [Configuration](https://github.com/tekkidev/mcpstat/blob/main/docs/configuration.md) - Customize paths, logging, presets
- [API Reference](https://github.com/tekkidev/mcpstat/blob/main/docs/api.md) - Complete method reference
- [Token Tracking](https://github.com/tekkidev/mcpstat/blob/main/docs/token-tracking.md) - Cost analysis features
- [Latency Tracking](https://github.com/tekkidev/mcpstat/blob/main/docs/latency-tracking.md) - Performance monitoring
- [Agent Documentation Index](https://mcpstat.vadim.dev/llms.txt) - Links to plain Markdown guides and examples
- [Full Agent Reference](https://mcpstat.vadim.dev/llms-full.txt) - Detailed integration and API summaries

## Examples

```bash
# Clone and run example server
git clone https://github.com/tekkidev/mcpstat.git
cd mcpstat
pip install -e ".[dev]"
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

<!-- mcp-name: io.github.tekkidev/mcpstat -->

---

*MCP is a trademark of its respective owners. This project is not affiliated with or endorsed by any trademark holders.*
