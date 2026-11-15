#!/usr/bin/env python3
"""
mcpstat - Usage tracking and analytics for MCP servers.
https://github.com/tekkidev/mcpstat

Copyright (c) 2026 Vadim Bakhrenkov
SPDX-License-Identifier: MIT

Call the weather example over stdio and verify its statistics and persistence.
Run with python examples/check_weather.py; each run uses temporary databases.
"""

import asyncio
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from mcp import Client
from mcp.client.stdio import StdioServerParameters


async def get_rows(client: Client) -> dict[str, Any]:
    result = await client.call_tool("get_tool_usage_stats", {})
    assert not result.is_error
    assert result.structured_content is not None
    return {row["name"]: row for row in result.structured_content["stats"]}


async def verify() -> None:
    with tempfile.TemporaryDirectory() as directory:
        for mode in ("auto", "legacy"):
            params = StdioServerParameters(
                command=sys.executable,
                args=[str(Path(__file__).with_name("weather_server.py"))],
                env={
                    "MCPSTAT_DB_PATH": str(Path(directory) / f"{mode}.sqlite"),
                    "MCPSTAT_LOG_ENABLED": "false",
                    "OTEL_SDK_DISABLED": "true",
                },
            )
            async with Client(params, mode=mode) as client:
                assert len((await client.list_tools()).tools) == 4
                baseline = await get_rows(client)
                assert all(row["call_count"] == 0 for row in baseline.values())
                for city in ("London", "Paris"):
                    result = await client.call_tool("get_weather", {"city": city})
                    assert not result.is_error
                    assert result.structured_content == {
                        "city": city,
                        "temperature_c": 21.0,
                        "condition": "synthetic sunshine",
                    }
                failure = await client.call_tool("fail_tool", {})
                assert failure.is_error
                assert failure.content[0].text.endswith("Intentional weather example failure")
                rows = await get_rows(client)
                assert rows["get_weather"]["call_count"] == 2
                assert rows["get_weather"]["success_count"] == 2
                assert rows["get_weather"]["error_count"] == 0
                assert rows["get_weather"]["duration_sample_count"] == 2
                assert rows["fail_tool"]["call_count"] == 1
                assert rows["fail_tool"]["error_count"] == 1
                assert rows["unused_tool"]["call_count"] == 0
                assert rows["get_tool_usage_stats"]["call_count"] == 0
                print(
                    json.dumps(
                        {
                            "mode": mode,
                            "stats": [
                                {
                                    key: rows[name][key]
                                    for key in (
                                        "name",
                                        "call_count",
                                        "success_count",
                                        "error_count",
                                        "duration_sample_count",
                                    )
                                }
                                for name in ("get_weather", "fail_tool", "unused_tool")
                            ],
                        }
                    )
                )
            async with Client(params, mode=mode) as client:
                persisted = await get_rows(client)
                for name in ("get_weather", "fail_tool", "unused_tool"):
                    for key in (
                        "call_count",
                        "success_count",
                        "error_count",
                        "duration_sample_count",
                    ):
                        assert persisted[name][key] == rows[name][key]
    print("Weather tool usage and restart persistence verified in both protocol modes")


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(verify(), timeout=60))
