#!/usr/bin/env python3
"""
mcpstat - Usage tracking and analytics for MCP servers.
https://github.com/tekkidev/mcpstat

Copyright (c) 2026 Vadim Bakhrenkov
SPDX-License-Identifier: MIT

Minimal MCP Server with mcpstat - Temperature Converter.

Shows:
- @stat.track decorator for automatic usage + latency tracking
- Simple, practical tools with one-line integration

Fun fact: -40°C = -40°F (the only temperature where both scales meet!)

Run:
    python minimal_server.py
"""

import asyncio
import json

import mcp_types as types
from jsonschema import Draft202012Validator
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp_types import TextContent, Tool

from mcpstat import MCPStat, disable_sdk_tracing

# =============================================================================
# Setup - Just 2 lines!
# =============================================================================

stat = MCPStat("temp-converter")  # That's it!


# =============================================================================
# Tools
# =============================================================================


async def list_tools() -> list[Tool]:
    tools = [
        Tool(
            name="celsius_to_fahrenheit",
            description="Convert temperature from Celsius to Fahrenheit",
            input_schema={
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
            input_schema={
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


@stat.track  # ← One decorator: tracks usage + latency automatically!
async def handle_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "celsius_to_fahrenheit":
        c = arguments["celsius"]
        f = (c * 9 / 5) + 32
        return [
            TextContent(
                type="text",
                text=json.dumps({"celsius": c, "fahrenheit": round(f, 2)}, allow_nan=False),
            )
        ]

    if name == "fahrenheit_to_celsius":
        f = arguments["fahrenheit"]
        c = (f - 32) * 5 / 9
        return [
            TextContent(
                type="text",
                text=json.dumps({"fahrenheit": f, "celsius": round(c, 2)}, allow_nan=False),
            )
        ]

    raise ValueError(f"Unknown tool: {name}")


# =============================================================================
# Run
# =============================================================================


async def _list_tools(_ctx, _params):
    return types.ListToolsResult(tools=await list_tools())


async def _call_tool(_ctx, params):
    try:
        arguments = params.arguments if params.arguments is not None else {}
        tool = next((tool for tool in await list_tools() if tool.name == params.name), None)
        if tool is None or not Draft202012Validator(tool.input_schema).is_valid(arguments):
            raise ValueError("Invalid tool arguments")
        return types.CallToolResult(content=await handle_tool(params.name, arguments))
    except (ValueError, TypeError, KeyError, OverflowError):
        return types.CallToolResult(
            content=[TextContent(type="text", text="Invalid tool request")], is_error=True
        )


app = Server("temp-converter", version="1.0.0", on_list_tools=_list_tools, on_call_tool=_call_tool)
disable_sdk_tracing(app)


async def main():
    """Run the stdio server and release logging resources on shutdown."""
    try:
        async with stdio_server() as (read, write):
            await app.run(read, write, app.create_initialization_options())
    finally:
        stat.close()


if __name__ == "__main__":
    asyncio.run(main())
