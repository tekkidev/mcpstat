"""
MCPStat - Usage tracking and analytics for MCP servers.
https://github.com/tekkidev/mcpstat

Copyright (c) 2026 Vadim Bakhrenkov
SPDX-License-Identifier: MIT

A pure-stdlib Python package for adding SQLite-backed usage statistics,
optional file logging, and built-in analytics to Model Context Protocol servers.

## Quick Start

```python
from mcp.server import Server
from mcpstat import MCPStat

app = Server("my-server")
stat = MCPStat("my-server")  # That's it!

@app.call_tool()
async def handle_tool(name: str, arguments: dict):
    await stat.record(name, "tool")
    # ... your logic
```

## Features

- 📊 SQLite-backed usage tracking for tools, prompts, resources
- 📝 Optional file-based audit logging
- 🔧 Built-in stats query functions
- 💬 Stats prompt generator for LLM consumption
- 🏷️ Metadata enrichment (tags, descriptions)
- ⚡ Async-first, thread-safe design
- 🔒 No required dependencies (pure Python stdlib)

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

__version__ = "0.1.2"
__author__ = "Vadim Bakhrenkov"
__license__ = "MIT"

from mcpstat.core import MCPStat
from mcpstat.database import MCPStatDatabase
from mcpstat.logging import MCPStatLogger
from mcpstat.prompts import build_prompt_definition, generate_stats_prompt
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
    "generate_stats_prompt",
    "normalize_tags",
]
