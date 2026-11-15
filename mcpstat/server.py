#!/usr/bin/env python3
"""
mcpstat - Usage tracking and analytics for MCP servers.
https://github.com/tekkidev/mcpstat

Copyright (c) 2026 Vadim Bakhrenkov
SPDX-License-Identifier: MIT

MCP Server for mcpstat - Documentation & Demo.

Serves mcpstat documentation as MCP resources and provides demo tools
with integrated self-tracking. This server uses mcpstat to track its
own usage - a self-referential proof of concept.

Features:
- Documentation resources (README, quickstart, API reference, etc.)
- Temperature conversion demo tools (Celsius ↔ Fahrenheit)
- Built-in usage statistics and tool catalog
- Stats prompt for LLM consumption
- Self-tracking: mcpstat monitors its own usage in real time

Run:
    python -m mcpstat.server
    # or via uvx (after PyPI install):
    uvx mcpstat
"""

from __future__ import annotations

import asyncio
import json
import os
from importlib.resources import files
from typing import TYPE_CHECKING, Any

import mcp_types as types
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from mcp.server import Server, ServerRequestContext
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
from platformdirs import user_data_path

from mcpstat import (
    BuiltinToolsHandler,
    MCPStat,
    __version__,
    build_tool_definitions,
    disable_sdk_tracing,
    generate_stats_prompt,
)

if TYPE_CHECKING:
    from importlib.resources.abc import Traversable

# =============================================================================
# Constants
# =============================================================================

SERVER_NAME = "mcpstat"
SERVER_VERSION = __version__

# Documentation files to expose as MCP resources
# Each entry: (resource_id, display_name, description, filename_relative_to_docs)
_DOC_RESOURCES: list[tuple[str, str, str, str]] = [
    ("readme", "README", "mcpstat overview and quick start guide", "README.md"),
    ("quickstart", "Quick Start", "Get running in 5 minutes", "docs/quickstart.md"),
    ("api", "API Reference", "Complete method reference for MCPStat", "docs/api.md"),
    ("configuration", "Configuration", "Paths, logging, metadata presets", "docs/configuration.md"),
    (
        "token-tracking",
        "Token Tracking",
        "Cost analysis and token estimation",
        "docs/token-tracking.md",
    ),
    (
        "latency-tracking",
        "Latency Tracking",
        "Performance monitoring and slow-tool detection",
        "docs/latency-tracking.md",
    ),
    ("llms-txt", "llms.txt", "Machine-readable project summary for AI agents", "llms.txt"),
    ("llms-full", "Full Agent Reference", "Complete machine-readable reference", "llms-full.txt"),
]


# =============================================================================
# Setup
# =============================================================================

_DATA_ROOT = user_data_path("mcpstat", appauthor=False)


# mcpstat tracking itself (self-referential!)
stat = MCPStat(
    SERVER_NAME,
    db_path=os.getenv("MCPSTAT_DB_PATH", str(_DATA_ROOT / "mcpstat_server_data.sqlite")),
    log_path=os.getenv("MCPSTAT_LOG_PATH", str(_DATA_ROOT / "mcpstat_server.log")),
    log_enabled=os.getenv("MCPSTAT_LOG_ENABLED", "false").lower() in ("true", "1", "yes"),
    metadata_presets={
        "celsius_to_fahrenheit": {
            "tags": ["temperature", "conversion", "demo"],
            "short": "Convert Celsius to Fahrenheit",
        },
        "fahrenheit_to_celsius": {
            "tags": ["temperature", "conversion", "demo"],
            "short": "Convert Fahrenheit to Celsius",
        },
        "get_tool_usage_stats": {
            "tags": ["analytics", "stats", "monitoring", "mcpstat"],
            "short": "Get usage statistics for all tracked primitives",
        },
        "get_tool_catalog": {
            "tags": ["discovery", "catalog", "search", "mcpstat"],
            "short": "Browse tools with tags and search",
        },
    },
)

stats_handler = BuiltinToolsHandler(stat, prefix="get")


# =============================================================================
# Tools
# =============================================================================


def _build_tool_list() -> list[Tool]:
    """Build the complete list of available tools."""
    custom_tools = [
        Tool(
            name="celsius_to_fahrenheit",
            description="Convert temperature from Celsius to Fahrenheit. Demo tool tracked by mcpstat.",
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
            description="Convert temperature from Fahrenheit to Celsius. Demo tool tracked by mcpstat.",
            input_schema={
                "type": "object",
                "properties": {
                    "fahrenheit": {
                        "type": "number",
                        "description": "Temperature in Fahrenheit",
                    },
                },
                "required": ["fahrenheit"],
            },
        ),
    ]

    # Built-in stats tools from mcpstat
    stats_tool_defs = build_tool_definitions(prefix="get", server_name=SERVER_NAME)
    stats_tools = [
        Tool(
            name=t["name"],
            description=t["description"],
            input_schema=t["inputSchema"],
            annotations=types.ToolAnnotations(
                read_only_hint=True, destructive_hint=False, open_world_hint=False
            ),
            output_schema={"type": "object", "additionalProperties": True},
        )
        for t in stats_tool_defs
    ]

    return custom_tools + stats_tools


_TOOL_VALIDATORS = {
    tool.name: Draft202012Validator(tool.input_schema) for tool in _build_tool_list()
}


async def list_tools() -> list[Tool]:
    """List available tools."""
    tools = _build_tool_list()
    await stat.sync_tools(tools)
    return tools


@stat.track  # ← mcpstat tracking its own server!
async def handle_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool execution with automatic self-tracking."""
    # Built-in stats tools
    if stats_handler.is_stats_tool(name):
        result = await stats_handler.handle(name, arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # Demo tools
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
# Resources (Documentation)
# =============================================================================


def _resolve_doc_path(filename: str) -> Traversable:
    return files("mcpstat").joinpath("_docs", filename)


async def list_resources() -> list[Resource]:
    """List documentation resources."""
    resources = []
    for res_id, display_name, description, filename in _DOC_RESOURCES:
        doc_path = _resolve_doc_path(filename)
        if doc_path.is_file():
            resources.append(
                Resource(
                    uri=f"resource://{SERVER_NAME}/{res_id}",
                    name=display_name,
                    description=description,
                    mime_type="text/markdown",
                )
            )

    # Dynamic resource: tool catalog
    resources.append(
        Resource(
            uri=f"resource://{SERVER_NAME}/tool-catalog",
            name="Tool Catalog",
            description="Live tag-indexed tool catalog with usage statistics",
            mime_type="text/markdown",
        ),
    )

    await stat.sync_resources(resources)
    return resources


async def read_resource(uri: str) -> str:
    """Read resource content with usage tracking."""
    uri_str = str(uri)
    resource_name = uri_str

    async with stat.tracking(resource_name, "resource"):
        # Check documentation resources
        for res_id, _display, _desc, filename in _DOC_RESOURCES:
            if uri_str == f"resource://{SERVER_NAME}/{res_id}":
                doc_path = _resolve_doc_path(filename)
                if doc_path.is_file():
                    return doc_path.read_text(encoding="utf-8")
                raise ValueError("Documentation resource is unavailable")

        # Dynamic: tool catalog
        if uri_str == f"resource://{SERVER_NAME}/tool-catalog":
            catalog = await stat.get_catalog(include_usage=True)
            lines = [
                "# Tool Catalog",
                "",
                f"**Server:** {SERVER_NAME} v{SERVER_VERSION}",
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
            description=(
                f"Generate {SERVER_NAME} usage statistics summary for tools, resources, and prompts"
            ),
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


@stat.track(primitive_type="prompt")
async def get_prompt(name: str, arguments: dict[str, Any] | None = None) -> GetPromptResult:
    """Get prompt with automatic tracking."""
    args = arguments or {}

    if name == "usage_stats":
        period = args.get("period", "all time")
        type_filter = args.get("type", "all")

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
# Entry point
# =============================================================================


async def _tools(
    _ctx: ServerRequestContext[Any], _params: types.PaginatedRequestParams | None
) -> types.ListToolsResult:
    return types.ListToolsResult(tools=await list_tools())


async def _call(
    _ctx: ServerRequestContext[Any], params: types.CallToolRequestParams
) -> types.CallToolResult:
    try:
        arguments = params.arguments if params.arguments is not None else {}
        validator = _TOOL_VALIDATORS.get(params.name)
        if validator is None or not validator.is_valid(arguments):
            raise ValueError("Invalid tool arguments")
        content = await handle_tool(params.name, arguments)
        return types.CallToolResult(
            content=[*content], structured_content=json.loads(content[0].text)
        )
    except (ValueError, TypeError, KeyError, OverflowError):
        return types.CallToolResult(
            content=[TextContent(type="text", text="Invalid tool request")], is_error=True
        )


async def _resources(
    _ctx: ServerRequestContext[Any], _params: types.PaginatedRequestParams | None
) -> types.ListResourcesResult:
    return types.ListResourcesResult(resources=await list_resources())


async def _read(
    _ctx: ServerRequestContext[Any], params: types.ReadResourceRequestParams
) -> types.ReadResourceResult:
    return types.ReadResourceResult(
        contents=[
            types.TextResourceContents(
                uri=params.uri, mime_type="text/markdown", text=await read_resource(params.uri)
            )
        ]
    )


async def _prompts(
    _ctx: ServerRequestContext[Any], _params: types.PaginatedRequestParams | None
) -> types.ListPromptsResult:
    return types.ListPromptsResult(prompts=await list_prompts())


async def _prompt(
    _ctx: ServerRequestContext[Any], params: types.GetPromptRequestParams
) -> types.GetPromptResult:
    return await get_prompt(params.name, params.arguments)


app = Server(
    SERVER_NAME,
    version=SERVER_VERSION,
    on_list_tools=_tools,
    on_call_tool=_call,
    on_list_resources=_resources,
    on_read_resource=_read,
    on_list_prompts=_prompts,
    on_get_prompt=_prompt,
    get_tool_input_schema=lambda name: next(
        (t.input_schema for t in _build_tool_list() if t.name == name), None
    ),
)
disable_sdk_tracing(app)


async def run_server() -> None:
    """Run the MCP server over standard input/output."""
    try:
        async with stdio_server() as (read, write):
            await app.run(read, write, app.create_initialization_options())
    finally:
        stat.close()


def main() -> None:
    """Run the mcpstat command."""
    os.environ["OTEL_SDK_DISABLED"] = "true"
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
