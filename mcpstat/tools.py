"""
mcpstat - Usage tracking and analytics for MCP servers.
https://github.com/tekkidev/mcpstat

Copyright (c) 2026 Vadim Bakhrenkov
SPDX-License-Identifier: MIT

Built-in tools for mcpstat.

Provides tool definitions and handlers for usage statistics and catalog queries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcpstat.core import MCPStat


def build_tool_definitions(
    prefix: str = "get",
    server_name: str = "MCP server",
) -> list[dict[str, Any]]:
    """Build tool definition dictionaries for MCP registration.

    Args:
        prefix: Prefix for tool names (e.g., "get" -> "get_tool_usage_stats")
        server_name: Server name for descriptions

    Returns:
        List of tool definition dictionaries
    """
    return [
        {
            "name": f"{prefix}_tool_usage_stats",
            "description": f"Get usage statistics for {server_name} (call counts and timestamps)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "include_zero_usage": {
                        "type": "boolean",
                        "default": True,
                        "description": "Include items that have never been invoked",
                    },
                    "type_filter": {
                        "type": "string",
                        "enum": ["tool", "prompt", "resource"],
                        "description": "Filter by primitive type (omit for all types)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of items to return (sorted by usage)",
                    },
                },
                "required": [],
            },
        },
        {
            "name": f"{prefix}_tool_catalog",
            "description": f"List {server_name} tools with tags, usage statistics, and text search",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter to tools containing all provided tags",
                    },
                    "query": {
                        "type": "string",
                        "description": "Text search across names, descriptions, and tags",
                    },
                    "include_usage": {
                        "type": "boolean",
                        "default": True,
                        "description": "Include usage counts and timestamps",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum entries to return",
                    },
                },
                "required": [],
            },
        },
    ]


class BuiltinToolsHandler:
    """Handler for built-in stats tools.

    Integrates with MCPStat to provide tool handlers.
    Use is_stats_tool() to check if a tool should be handled here.
    """

    __slots__ = ("_names", "prefix", "stat")

    def __init__(self, stat: MCPStat, prefix: str = "get") -> None:
        """Initialize handler.

        Args:
            stat: MCPStat instance
            prefix: Prefix for tool names
        """
        self.stat = stat
        self.prefix = prefix
        self._names = {
            f"{prefix}_tool_usage_stats",
            f"{prefix}_tool_catalog",
        }

    def is_stats_tool(self, name: str) -> bool:
        """Check if tool name is a built-in stats tool."""
        return name in self._names

    async def handle(self, name: str, arguments: dict[str, Any]) -> dict[str, Any] | None:
        """Handle a built-in tool call.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            Tool result or None if not a stats tool
        """
        if name == f"{self.prefix}_tool_usage_stats":
            return await self.stat.get_stats(
                include_zero=arguments.get("include_zero_usage", True),
                limit=arguments.get("limit"),
                type_filter=arguments.get("type_filter"),
            )

        if name == f"{self.prefix}_tool_catalog":
            return await self.stat.get_catalog(
                tags=arguments.get("tags"),
                query=arguments.get("query"),
                include_usage=arguments.get("include_usage", True),
                limit=arguments.get("limit"),
            )

        return None
