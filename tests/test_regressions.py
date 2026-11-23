"""
mcpstat - Usage tracking and analytics for MCP servers.
https://github.com/tekkidev/mcpstat

Copyright (c) 2026 Vadim Bakhrenkov
SPDX-License-Identifier: MIT

Regression coverage for persistent identities, outcomes, and resource isolation.
"""

import asyncio
import json
import threading
from types import SimpleNamespace

import pytest
from mcp_types import CallToolResult

from mcpstat import MCPStat, MCPStatDatabase, MCPStatLogger


@pytest.mark.parametrize("logging", [False, True])
async def test_record_dispatches_only_enabled_file_logging(tmp_path, monkeypatch, logging):
    """Disabled logs avoid a worker dispatch without losing persisted statistics."""
    monkeypatch.setenv("MCPSTAT_LOG_ENABLED", str(logging).lower())
    log_path = tmp_path / "usage.jsonl"
    tracker = MCPStat("synthetic", db_path=str(tmp_path / "stats.sqlite"), log_path=str(log_path))
    original = asyncio.to_thread
    dispatched = []

    async def observe(fn, *args, **kwargs):
        dispatched.append(fn)
        return await original(fn, *args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", observe)
    try:
        await tracker.record("synthetic_tool", error_msg="synthetic-private-value")
        assert len(dispatched) == (2 if logging else 1)
        row = (await tracker.get_stats())["stats"][0]
        assert row["call_count"] == row["success_count"] == 1
        assert log_path.exists() is logging
        if logging:
            line = json.loads(log_path.read_text())
            assert line["name"] == "synthetic_tool"
            assert "synthetic-private-value" not in log_path.read_text()
    finally:
        tracker.close()


async def test_identity_and_history(tmp_path):
    path = str(tmp_path / "stats.sqlite")
    first, second = MCPStat("first", db_path=path), MCPStat("second", db_path=path)
    await first.record("same", "tool")
    await first.record("same", "prompt")
    await second.record("same", "tool")
    await first.sync_tools(
        [
            SimpleNamespace(name="same", description=""),
            SimpleNamespace(name="unused", description=""),
        ]
    )
    rows = (await first.get_stats())["stats"]
    assert len(rows) == 3
    assert sum(r["call_count"] for r in rows) == 2
    assert (await second.get_stats())["total_calls"] == 1
    await first.sync_tools([])
    assert (await first.get_stats())["total_calls"] == 2
    assert (await first.get_catalog())["results"] == []


async def test_outcomes(tmp_path):
    tracker = MCPStat("outcomes", db_path=str(tmp_path / "stats.sqlite"))

    @tracker.track(name="returned_error")
    async def error():
        return CallToolResult(content=[], is_error=True)

    @tracker.track(name="cancelled")
    async def cancel():
        raise asyncio.CancelledError

    await error()
    with pytest.raises(asyncio.CancelledError):
        await cancel()
    with pytest.raises(asyncio.CancelledError):
        async with tracker.tracking("context_cancel"):
            raise asyncio.CancelledError
    rows = {r["name"]: r for r in (await tracker.get_stats())["stats"]}
    assert rows["returned_error"]["error_count"] == 1
    assert rows["cancelled"]["cancelled_count"] == 1
    assert rows["context_cancel"]["cancelled_count"] == 1


async def test_concurrent_instances(tmp_path):
    path = str(tmp_path / "stats.sqlite")
    instances = [MCPStatDatabase(path) for _ in range(4)]
    await asyncio.gather(*(instances[i % 4].record("tool") for i in range(40)))
    assert (await instances[0].get_stats())["total_calls"] == 40


async def test_database_work_does_not_block_loop(tmp_path, monkeypatch):
    db = MCPStatDatabase(str(tmp_path / "stats.sqlite"))
    entered, release = threading.Event(), threading.Event()
    original = db._ensure_schema

    def wait(conn):
        entered.set()
        assert release.wait(2)
        original(conn)

    monkeypatch.setattr(db, "_ensure_schema", wait)
    task = asyncio.create_task(db.record("tool"))
    try:
        for _ in range(100):
            if entered.is_set():
                break
            await asyncio.sleep(0.01)
        assert entered.is_set()
    finally:
        release.set()
    await task


def test_log_isolation_and_escaping(tmp_path):
    first, second = (
        MCPStatLogger(str(tmp_path / "first.log")),
        MCPStatLogger(str(tmp_path / "second.log")),
    )
    first.close()
    second.log("tool\nforged", "tool", success=False, error_msg="secret-value")
    second.close()
    lines = (tmp_path / "second.log").read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["name"] == "tool\nforged"
    assert "secret-value" not in lines[0]
    assert not (tmp_path / "first.log").read_text()


async def test_limits_and_token_validation(tmp_path):
    db = MCPStatDatabase(str(tmp_path / "stats.sqlite"))
    for limit in (-1, 0, 1001, True):
        with pytest.raises(ValueError):
            await db.get_stats(limit=limit)
    with pytest.raises(ValueError):
        await db.record("tool", input_tokens=-1)
    with pytest.raises(ValueError):
        await db.report_tokens("unknown", 1, 2)


async def test_future_schema_is_not_overwritten(tmp_path):
    import sqlite3
    from contextlib import closing

    path = str(tmp_path / "future.sqlite")
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA user_version=99")
    with pytest.raises(ValueError, match="newer"):
        await MCPStatDatabase(path).get_stats()
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 99


async def test_catalog_without_usage_omits_counters(tmp_path):
    tracker = MCPStat("catalog", db_path=str(tmp_path / "stats.sqlite"))
    await tracker.sync_tools([SimpleNamespace(name="tool", description="Example")])
    await tracker.record("tool", input_tokens=10)
    row = (await tracker.get_catalog(include_usage=False))["results"][0]
    assert row["call_count"] is None
    assert "total_input_tokens" not in row


@pytest.mark.parametrize("invalid", ["false", 0, 1, None, [], {}])
async def test_query_boolean_flags_are_strict(tmp_path, invalid):
    db = MCPStatDatabase(str(tmp_path / "stats.sqlite"))
    with pytest.raises(ValueError, match="include_zero must be a boolean"):
        await db.get_stats(include_zero=invalid)
    with pytest.raises(ValueError, match="include_usage must be a boolean"):
        await db.get_catalog(include_usage=invalid)
