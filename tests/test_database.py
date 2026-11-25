"""
mcpstat - Usage tracking and analytics for MCP servers.
https://github.com/tekkidev/mcpstat

Copyright (c) 2026 Vadim Bakhrenkov
SPDX-License-Identifier: MIT

Database validation, contention recovery, and migration integrity tests.
"""

import sqlite3
from contextlib import closing

import pytest

from mcpstat import MCPStatDatabase


def test_database_requires_file_backing():
    with pytest.raises(ValueError, match="file-backed"):
        MCPStatDatabase(":memory:")


@pytest.mark.parametrize(
    ("operation", "arguments", "message"),
    [
        ("record", {"name": ""}, "name must contain"),
        ("record", {"name": 42}, "name must contain"),
        ("record", {"name": "x" * 2049}, "name must contain"),
        ("record", {"name": "tool", "primitive_type": "unknown"}, "primitive_type"),
        ("record", {"name": "tool", "outcome": "unknown"}, "Invalid outcome"),
        ("record", {"name": "tool", "response_chars": True}, "nonnegative integers"),
        ("record", {"name": "tool", "output_tokens": 1.5}, "nonnegative integers"),
        ("report_tokens", {"name": "tool", "input_tokens": -1, "output_tokens": 0}, "Token counts"),
        (
            "report_tokens",
            {"name": "tool", "input_tokens": 0, "output_tokens": True},
            "Token counts",
        ),
        ("get_stats", {"type_filter": "unknown"}, "Invalid type_filter"),
        ("sync_metadata", {"tools": [], "primitive_type": "unknown"}, "Invalid primitive_type"),
        ("get_catalog", {"query": 42}, "query must be a string"),
        ("get_catalog", {"query": "x" * 1025}, "query must be a string"),
        ("get_catalog", {"tags": ("tag",)}, "tags must contain"),
        ("get_catalog", {"tags": ["tag"] * 51}, "tags must contain"),
        ("get_catalog", {"tags": [42]}, "tags must contain"),
        ("get_catalog", {"tags": ["x" * 101]}, "tags must contain"),
    ],
)
async def test_invalid_requests_do_not_create_database(tmp_path, operation, arguments, message):
    path = tmp_path / "invalid.sqlite"
    db = MCPStatDatabase(str(path))
    with pytest.raises(ValueError, match=message):
        await getattr(db, operation)(**arguments)
    assert not path.exists()


@pytest.mark.parametrize(
    ("failures", "expected_delays", "raises"),
    [
        (["database is locked"] * 2, [0.01, 0.02], False),
        (["database is locked"] * 4, [0.01, 0.02, 0.03], True),
        (["disk I/O error"], [], True),
    ],
)
async def test_wal_retries_are_bounded_and_connections_close(
    tmp_path, monkeypatch, failures, expected_delays, raises
):
    """Retry lock contention only; close failed connections and permit later recovery."""
    from mcpstat import database

    original_connect = sqlite3.connect
    connections, closed_connections, delays, attempts = [], [], [], []

    class ContendedConnection(sqlite3.Connection):
        def execute(self, statement, *args, **kwargs):
            if statement == "PRAGMA journal_mode=WAL":
                attempts.append(statement)
                if len(attempts) <= len(failures):
                    raise sqlite3.OperationalError(failures[len(attempts) - 1])
            return super().execute(statement, *args, **kwargs)

        def close(self):
            super().close()
            with pytest.raises(sqlite3.ProgrammingError, match="closed"):
                super().execute("SELECT 1")
            closed_connections.append(self)

    def connect(*args, **kwargs):
        connection = original_connect(*args, factory=ContendedConnection, **kwargs)
        connections.append(connection)
        return connection

    monkeypatch.setattr(database.sqlite3, "connect", connect)
    monkeypatch.setattr(database.time, "sleep", delays.append)
    db = MCPStatDatabase(str(tmp_path / "contended.sqlite"))
    if raises:
        with pytest.raises(sqlite3.OperationalError, match=failures[-1]):
            await db.record("tool")
    else:
        await db.record("tool")
    assert delays == expected_delays
    assert len(attempts) == len(expected_delays) + 1
    assert closed_connections == connections

    monkeypatch.setattr(database.sqlite3, "connect", original_connect)
    await db.record("recovered")
    assert (await db.get_stats())["total_calls"] == (1 if raises else 2)


async def test_legacy_metadata_preserves_identity_and_orphans(tmp_path):
    """Migration retains descriptions, parsed tags and metadata without usage rows."""
    path = tmp_path / "legacy.sqlite"
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript("""
            CREATE TABLE mcpstat_usage (
                name TEXT, type TEXT, call_count INTEGER,
                last_accessed TEXT, created_at TEXT
            );
            CREATE TABLE mcpstat_metadata (
                name TEXT, tags TEXT, short_description TEXT, full_description TEXT
            );
            INSERT INTO mcpstat_usage VALUES ('legacy', 'prompt', 4, NULL, NULL);
            INSERT INTO mcpstat_metadata VALUES
                ('legacy', ' report, summary ', 'Summary', 'Generate a summary'),
                ('unused', NULL, NULL, NULL);
        """)

    db = MCPStatDatabase(str(path), "synthetic")
    rows = {row["name"]: row for row in (await db.get_stats())["stats"]}
    assert rows["legacy"]["type"] == "prompt"
    assert rows["legacy"]["call_count"] == 4
    assert rows["legacy"]["tags"] == ["report", "summary"]
    assert rows["legacy"]["short_description"] == "Summary"
    assert rows["legacy"]["full_description"] == "Generate a summary"
    assert rows["unused"]["type"] == "tool"
    assert rows["unused"]["call_count"] == 0
    assert rows["unused"]["tags"] == []
    assert rows["unused"]["short_description"] == ""
    assert rows["unused"]["full_description"] == ""
    await db.record("legacy", "prompt")
    assert (await db.get_stats())["total_calls"] == 5


async def test_invalid_metadata_sync_rolls_back_entire_batch(tmp_path):
    db = MCPStatDatabase(str(tmp_path / "metadata.sqlite"))
    await db.update_metadata("existing", tags=["kept"], short_description="Existing")
    with pytest.raises(ValueError, match="name must contain"):
        await db.sync_metadata([{"name": "pending"}, {"name": ""}])
    rows = (await db.get_catalog())["results"]
    assert [row["name"] for row in rows] == ["existing"]
    assert rows[0]["tags"] == ["kept"]
