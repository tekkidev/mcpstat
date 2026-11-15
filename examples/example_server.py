#!/usr/bin/env python3
"""
mcpstat - Usage tracking and analytics for MCP servers.
https://github.com/tekkidev/mcpstat

Copyright (c) 2026 Vadim Bakhrenkov
SPDX-License-Identifier: MIT

Extended MCP Server Example - Temperature Converter with Stats & Resources.

Demonstrates:
- @stat.track decorator for automatic usage + latency tracking (tools)
- @stat.track(primitive_type=...) for prompt tracking
- stat.tracking() context manager for resource tracking
- Built-in stats prompt for LLM consumption
- Resource exposure (README.md)
- Metadata presets for tool discovery

Fun fact: -40°C = -40°F (the only temperature where both scales meet!)

Run:
    python example_server.py
"""

import asyncio
import json
import os
from pathlib import Path

import mcp_types as types
from jsonschema import Draft202012Validator
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp_types import (
    GetPromptResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    Resource,
    TextContent,
    Tool,
)

from mcpstat import (
    BuiltinToolsHandler,
    MCPStat,
    build_tool_definitions,
    disable_sdk_tracing,
    generate_stats_prompt,
)

# =============================================================================
# Setup
# =============================================================================

_HERE = Path(__file__).parent


# Initialize mcpstat with metadata presets for better tool discovery
stat = MCPStat(
    "example-server",
    db_path=str(_HERE / "example_stats.sqlite"),
    log_path=str(_HERE / "example_stats.log"),
    log_enabled=os.getenv("MCPSTAT_LOG_ENABLED", "false").lower() in ("true", "1", "yes"),
    metadata_presets={
        "celsius_to_fahrenheit": {
            "tags": ["temperature", "conversion", "math"],
            "short": "Convert Celsius to Fahrenheit",
        },
        "fahrenheit_to_celsius": {
            "tags": ["temperature", "conversion", "math"],
            "short": "Convert Fahrenheit to Celsius",
        },
        "get_tool_usage_stats": {
            "tags": ["analytics", "stats", "monitoring"],
            "short": "Get usage statistics for all tools",
        },
        "get_tool_catalog": {
            "tags": ["discovery", "catalog", "search"],
            "short": "Browse tools with tags and search",
        },
    },
)

# Handler for built-in stats tools
stats_handler = BuiltinToolsHandler(stat, prefix="get")

# Path to README.md (one level up from examples/)
README_PATH = _HERE.parent / "README.md"


# =============================================================================
# Tools
# =============================================================================


def _build_tool_list() -> list[Tool]:
    """Build the list of available tools."""
    # Custom tools
    custom_tools = [
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

    # Built-in stats tools from mcpstat
    stats_tool_defs = build_tool_definitions(prefix="get", server_name="example-server")
    stats_tools = [
        Tool(
            name=t["name"],
            description=t["description"],
            input_schema=t["inputSchema"],
        )
        for t in stats_tool_defs
    ]

    return custom_tools + stats_tools


async def list_tools() -> list[Tool]:
    """List available tools."""
    tools = _build_tool_list()
    await stat.sync_tools(tools)
    return tools


@stat.track  # ← Automatic usage + latency tracking!
async def handle_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool execution with automatic usage tracking."""
    # Handle built-in stats tools
    if stats_handler.is_stats_tool(name):
        result = await stats_handler.handle(name, arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # Custom tools
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

    # Unknown tool (still tracked above)
    raise ValueError(f"Unknown tool: {name}")


# =============================================================================
# Resources
# =============================================================================


async def list_resources() -> list[Resource]:
    """List available resources."""
    resources = [
        Resource(
            uri="resource://example-server/readme",
            name="README.md",
            description="mcpstat package documentation and usage guide",
            mime_type="text/markdown",
        ),
        Resource(
            uri="resource://example-server/tool-catalog",
            name="Tool Catalog",
            description="Tag-indexed tool catalog with usage statistics",
            mime_type="text/markdown",
        ),
    ]
    await stat.sync_resources(resources)
    return resources


async def read_resource(uri: str) -> str:
    """Read resource content with usage tracking via context manager."""
    # Extract resource name for tracking
    # Convert AnyUrl to string if needed (MCP SDK may pass AnyUrl instead of str)
    uri_str = str(uri)
    resource_name = uri_str

    # Use tracking() context manager when you need to compute the name first
    async with stat.tracking(resource_name, "resource"):
        if uri_str == "resource://example-server/readme":
            if README_PATH.exists():
                return README_PATH.read_text(encoding="utf-8")
            return (
                "# README not found\n\nThe README.md file was not found at the expected location."
            )

        if uri_str == "resource://example-server/tool-catalog":
            catalog = await stat.get_catalog(include_usage=True)
            lines = [
                "# Tool Catalog",
                "",
                f"**Total tools:** {catalog['total_tracked']}",
                f"**Available tags:** {', '.join(catalog.get('all_tags', []))}",
                "",
                "## Tools",
                "",
            ]
            for entry in catalog["results"]:
                tags = ", ".join(entry.get("tags", [])) or "(no tags)"
                calls = entry.get("call_count", 0)
                lines.append(f"### `{entry['name']}`")
                lines.append(entry.get("short_description", ""))
                lines.append(f"- **Tags:** {tags}")
                lines.append(f"- **Calls:** {calls}")
                lines.append("")
            return "\n".join(lines)

        raise ValueError(f"Unknown resource: {uri_str}")


# =============================================================================
# Prompts
# =============================================================================


async def list_prompts() -> list[Prompt]:
    """List available prompts."""
    prompts = [
        Prompt(
            name="usage_stats",
            description="Generate MCP usage statistics summary for tools, resources, and prompts",
            arguments=[
                PromptArgument(
                    name="period",
                    description="Reporting period: all time",
                    required=False,
                ),
                PromptArgument(
                    name="type",
                    description="Filter by type: 'all', 'tool', 'resource', 'prompt'",
                    required=False,
                ),
            ],
        ),
    ]
    await stat.sync_prompts(prompts)
    return prompts


@stat.track(primitive_type="prompt")  # ← Decorator with explicit type
async def get_prompt(name: str, arguments: dict | None = None) -> GetPromptResult:
    """Get prompt with automatic tracking."""
    args = arguments or {}

    if name == "usage_stats":
        period = args.get("period", "all time")
        type_filter = args.get("type", "all")

        # Generate stats prompt using mcpstat
        prompt_text = await generate_stats_prompt(
            stat,
            period=period,
            type_filter=type_filter,
            include_recommendations=True,
        )

        return GetPromptResult(
            description=f"MCP usage statistics for {period}",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=prompt_text),
                )
            ],
        )

    raise ValueError(f"Unknown prompt: {name}")


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


async def _list_resources(_ctx, _params):
    return types.ListResourcesResult(resources=await list_resources())


async def _read_resource(_ctx, params):
    return types.ReadResourceResult(
        contents=[
            types.TextResourceContents(
                uri=params.uri, mime_type="text/markdown", text=await read_resource(params.uri)
            )
        ]
    )


async def _list_prompts(_ctx, _params):
    return types.ListPromptsResult(prompts=await list_prompts())


async def _get_prompt(_ctx, params):
    return await get_prompt(params.name, params.arguments)


app = Server(
    "example-server",
    version="1.0.0",
    on_list_tools=_list_tools,
    on_call_tool=_call_tool,
    on_list_resources=_list_resources,
    on_read_resource=_read_resource,
    on_list_prompts=_list_prompts,
    on_get_prompt=_get_prompt,
)
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
