"""
mcpstat - Usage tracking and analytics for MCP servers.
https://github.com/tekkidev/mcpstat

Copyright (c) 2026 Vadim Bakhrenkov
SPDX-License-Identifier: MIT

A Python package for adding SQLite-backed usage statistics, optional file
logging, and built-in analytics to Model Context Protocol servers.
The server integration uses MCP SDK >=2.3,<3; the tracking core is SDK-independent.

## Quick Start

```python
from mcp.server import MCPServer
from mcpstat import MCPStat, disable_sdk_tracing

app = MCPServer("my-server")
disable_sdk_tracing(app)
stat = MCPStat("my-server")

# One decorator - automatic latency tracking!
@app.tool()
@stat.track(name="echo")
async def echo(message: str) -> str:
    # Return a message.
    return message
```

## Features

- SQLite-backed usage tracking for tools, prompts, resources
- **Automatic latency tracking** via `@stat.track` decorator
- Optional file-based audit logging
- Built-in stats query functions
- Stats prompt generator for LLM consumption
- Metadata enrichment (tags, descriptions)
- Async-first design with database operations in worker threads
- Server integration supports MCP SDK >=2.3,<3

## Configuration

All settings are passed at initialization:

```python
stat = MCPStat(
    server_name="my-server",
    db_path="./my_mcp_data.sqlite",
    log_path="./my_mcp.log",
    log_enabled=True,
    metadata_presets={
        "my_tool": {"tags": ["api"], "short": "My tool description"}
    }
)
```

Environment variables (optional override):
- `MCPSTAT_DB_PATH`: SQLite database path
- `MCPSTAT_LOG_PATH`: Log file path
- `MCPSTAT_LOG_ENABLED`: Enable file logging (true/1/yes)
"""

from __future__ import annotations

__version__ = "0.3.1"
__author__ = "Vadim Bakhrenkov"
__license__ = "MIT"

from mcpstat.core import MCPStat
from mcpstat.database import MCPStatDatabase
from mcpstat.logging import MCPStatLogger
from mcpstat.prompts import build_prompt_definition, generate_stats_prompt
from mcpstat.sdk import disable_sdk_tracing
from mcpstat.tools import BuiltinToolsHandler, build_tool_definitions
from mcpstat.utils import derive_short_description, normalize_tags

__all__ = [
    "BuiltinToolsHandler",
    "MCPStat",
    "MCPStatDatabase",
    "MCPStatLogger",
    "__version__",
    "build_prompt_definition",
    "build_tool_definitions",
    "derive_short_description",
    "disable_sdk_tracing",
    "generate_stats_prompt",
    "normalize_tags",
]
