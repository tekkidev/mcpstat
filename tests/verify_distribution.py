"""
mcpstat - Usage tracking and analytics for MCP servers.
https://github.com/tekkidev/mcpstat

Copyright (c) 2026 Vadim Bakhrenkov
SPDX-License-Identifier: MIT

Verify an installed distribution using local stdio MCP subprocesses.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from importlib.metadata import distribution
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

import mcpstat


async def verify() -> None:
    assert mcpstat.__version__ == distribution("mcpstat").version
    assert Path(mcpstat.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()), (
        "Run with an isolated wheel installation outside the source checkout"
    )
    installed_files = [str(path) for path in distribution("mcpstat").files or ()]
    assert "ThirdPartyNotices.md" in installed_files, "Third-party notices are missing"
    assert len(installed_files) == len(set(installed_files)), "Duplicate distribution paths"
    with tempfile.TemporaryDirectory() as directory:
        for mode in ("auto", "legacy"):
            params = StdioServerParameters(
                command=sys.executable,
                args=["-m", "mcpstat.server"],
                env={
                    "MCPSTAT_DB_PATH": str(Path(directory) / f"{mode}.sqlite"),
                    "MCPSTAT_LOG_ENABLED": "false",
                    "OTEL_SDK_DISABLED": "true",
                    "OTEL_PROPAGATORS": "none",
                },
            )
            async with Client(params, mode=mode) as client:
                listing = await client.list_tools()
                assert len(listing.tools) == 4
                result = await client.call_tool("celsius_to_fahrenheit", {"celsius": 100})
                assert not result.is_error
                assert result.structured_content["fahrenheit"] == 212
                result = await client.call_tool("fahrenheit_to_celsius", {"fahrenheit": 32})
                assert result.structured_content["celsius"] == 0
                stats = await client.call_tool("get_tool_usage_stats", {})
                rows = stats.structured_content["stats"]
                assert (
                    next(r for r in rows if r["name"] == "celsius_to_fahrenheit")["call_count"] == 1
                )
                catalog = await client.call_tool("get_tool_catalog", {"tags": ["demo"]})
                assert catalog.structured_content["matched"] == 2
                resources = await client.list_resources()
                assert len(resources.resources) == 9
                for resource in resources.resources:
                    result = await client.read_resource(resource.uri)
                    assert result.contents[0].text
                assert (await client.list_prompts()).prompts
                prompt = await client.get_prompt("usage_stats", {"period": "all time"})
                assert "MCP Usage Statistics" in prompt.messages[0].content.text
                for name, arguments in (
                    ("celsius_to_fahrenheit", {"celsius": True}),
                    ("celsius_to_fahrenheit", {"celsius": "12"}),
                    ("celsius_to_fahrenheit", {}),
                    ("get_tool_usage_stats", {"include_zero_usage": "false"}),
                    ("get_tool_usage_stats", {"limit": -1}),
                    ("get_tool_catalog", {"include_usage": "false"}),
                    ("get_tool_catalog", {"tags": "demo"}),
                ):
                    invalid = await client.call_tool(name, arguments)
                    assert invalid.is_error, (mode, name, arguments)
                    assert invalid.content[0].text == "Invalid tool request"
                hidden_usage = await client.call_tool("get_tool_catalog", {"include_usage": False})
                assert hidden_usage.structured_content["total_calls"] is None
                assert all(
                    row["call_count"] is None for row in hidden_usage.structured_content["results"]
                )
            async with Client(params, mode=mode) as client:
                stats = await client.call_tool("get_tool_usage_stats", {})
                assert (
                    next(
                        r
                        for r in stats.structured_content["stats"]
                        if r["name"] == "celsius_to_fahrenheit"
                    )["call_count"]
                    == 1
                )
    print(
        "Installed distribution: stdio tools, resources, prompts, errors, and persistence verified"
    )


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(verify(), timeout=60))
