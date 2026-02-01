#!/usr/bin/env python3
"""
mcpstat - Usage tracking and analytics for MCP servers.
https://github.com/tekkidev/mcpstat

Copyright (c) 2026 Vadim Bakhrenkov
SPDX-License-Identifier: MIT

Minimal MCP Server with mcpstat - Temperature Converter.

Shows:
- 3 lines to add stats tracking to any MCP server
- Simple, practical tools with usage recording

Fun fact: -40°C = -40°F (the only temperature where both scales meet!)

Run:
    python minimal_server.py
"""

import asyncio
import json

from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from mcpstat import MCPStat

# =============================================================================
# Setup - Just 3 lines!
# =============================================================================

app = Server("temp-converter")
stat = MCPStat("temp-converter")  # That's it!


# =============================================================================
# Tools
# =============================================================================


@app.list_tools()
async def list_tools() -> list[Tool]:
    tools = [
        Tool(
            name="celsius_to_fahrenheit",
            description="Convert temperature from Celsius to Fahrenheit",
            inputSchema={
                "type": "object",
                "properties": {
                    "celsius": {"type": "number", "description": "Temperature in Celsius"},
                },
                "required": ["celsius"],
            },
        ),
        Tool(
            name="fahrenheit_to_celsius",
            description="Convert temperature from Fahrenheit to Celsius",
            inputSchema={
                "type": "object",
                "properties": {
                    "fahrenheit": {"type": "number", "description": "Temperature in Fahrenheit"},
                },
                "required": ["fahrenheit"],
            },
        ),
    ]
    await stat.sync_tools(tools)  # Optional: enables catalog queries
    return tools


@app.call_tool()
async def handle_tool(name: str, arguments: dict) -> list[TextContent]:
    # Record usage - add this ONE line to every handler
    await stat.record(name, "tool")

    if name == "celsius_to_fahrenheit":
        c = arguments.get("celsius", 0)
        f = (c * 9 / 5) + 32
        return [
            TextContent(type="text", text=json.dumps({"celsius": c, "fahrenheit": round(f, 2)}))
        ]

    if name == "fahrenheit_to_celsius":
        f = arguments.get("fahrenheit", 0)
        c = (f - 32) * 5 / 9
        return [
            TextContent(type="text", text=json.dumps({"fahrenheit": f, "celsius": round(c, 2)}))
        ]

    return [TextContent(type="text", text=json.dumps({"error": "Unknown tool"}))]


# =============================================================================
# Run
# =============================================================================


async def main():
    async with stdio_server() as (read, write):
        await app.run(
            read,
            write,
            InitializationOptions(
                server_name="temp-converter",
                server_version="1.0.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
