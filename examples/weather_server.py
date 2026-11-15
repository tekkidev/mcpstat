#!/usr/bin/env python3
"""
mcpstat - Usage tracking and analytics for MCP servers.
https://github.com/tekkidev/mcpstat

Copyright (c) 2026 Vadim Bakhrenkov
SPDX-License-Identifier: MIT

Instrument an independent MCP server with synthetic weather tools.
Run with python examples/weather_server.py or use check_weather.py as a client.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from mcpstat import MCPStat, disable_sdk_tracing

stat = MCPStat("weather", db_path="./weather_stats.sqlite")


@asynccontextmanager
async def lifespan(server: MCPServer) -> AsyncIterator[dict[str, Any]]:
    try:
        await stat.sync_tools(await server.list_tools())
        yield {}
    finally:
        stat.close()


app = MCPServer("weather", lifespan=lifespan)
disable_sdk_tracing(app)


@app.tool()
@stat.track(name="get_weather")
async def get_weather(city: str) -> dict[str, Any]:
    """Return synthetic weather without contacting an external service."""
    return {"city": city, "temperature_c": 21.0, "condition": "synthetic sunshine"}


@app.tool()
@stat.track(name="unused_tool")
async def unused_tool() -> str:
    """An uncalled tool demonstrates zero-use statistics."""
    return "Unused example"


@app.tool()
@stat.track(name="fail_tool")
async def fail_tool() -> str:
    """Return an intentional MCP tool error to demonstrate failure tracking."""
    raise ToolError("Intentional weather example failure")


@app.tool()
async def get_tool_usage_stats() -> dict[str, Any]:
    """Return cumulative usage and latency statistics without counting this query."""
    return await stat.get_stats()


if __name__ == "__main__":
    app.run()
