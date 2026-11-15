"""
mcpstat - Usage tracking and analytics for MCP servers.
https://github.com/tekkidev/mcpstat

Copyright (c) 2026 Vadim Bakhrenkov
SPDX-License-Identifier: MIT

SQLite database management for mcpstat.

Provides schema creation, transactional migrations, atomic usage updates, metadata
synchronization, and catalog queries. Worker threads keep SQLite I/O off the event loop;
a per-instance lock and SQLite transactions coordinate access.
"""

from __future__ import annotations

import asyncio
import functools
import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Iterator

P = ParamSpec("P")
T = TypeVar("T")
SCHEMA_VERSION = 4
CHARS_PER_TOKEN = 3.5
_TYPES = {"tool", "prompt", "resource"}
_COUNTERS = (
    "call_count",
    "total_input_tokens",
    "total_output_tokens",
    "total_response_chars",
    "estimated_tokens",
    "total_duration_ms",
    "duration_sample_count",
    "success_count",
    "error_count",
    "cancelled_count",
    "incomplete_count",
)


def _worker(fn: Callable[P, T]) -> Callable[P, Coroutine[Any, Any, T]]:
    @functools.wraps(fn)
    async def run(*args: P.args, **kwargs: P.kwargs) -> T:
        return await asyncio.to_thread(fn, *args, **kwargs)

    return run


def _identity(name: str, primitive_type: str) -> None:
    if not isinstance(name, str) or not name or len(name) > 2048:
        raise ValueError("name must contain between 1 and 2048 characters")
    if primitive_type not in _TYPES:
        raise ValueError("primitive_type must be tool, prompt, or resource")


def _limit(limit: int | None) -> int:
    if limit is None:
        return 1000
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    return limit


class MCPStatDatabase:
    """File-backed statistics; each operation runs in a worker thread.

    A lock serializes operations for this instance. SQLite transactions coordinate
    independent instances and processes. Each SQLite contention wait is limited to one second. WAL setup uses at most
    four attempts to handle concurrent initialization.
    """

    def __init__(self, db_path: str, server_name: str = "") -> None:
        if db_path == ":memory:":
            raise ValueError("Use a file-backed database")
        self.db_path = db_path
        self.server_name = server_name
        self._lock = threading.RLock()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.db_path, timeout=1.0)
            conn.row_factory = sqlite3.Row
            try:
                for attempt in range(4):
                    try:
                        conn.execute("PRAGMA journal_mode=WAL")
                        break
                    except sqlite3.OperationalError as exc:
                        if "locked" not in str(exc) or attempt == 3:
                            raise
                        time.sleep(0.01 * (attempt + 1))
                conn.execute("BEGIN IMMEDIATE")
                self._ensure_schema(conn)
                yield conn
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise ValueError("Database schema is newer than this package")
        if version == SCHEMA_VERSION:
            return
        columns = {r[1] for r in conn.execute("PRAGMA table_info(mcpstat_usage)")}
        migrate = bool(columns) and "server" not in columns
        if migrate:
            conn.execute("ALTER TABLE mcpstat_usage RENAME TO mcpstat_usage_previous")
            conn.execute("ALTER TABLE mcpstat_metadata RENAME TO mcpstat_metadata_previous")
        counters = ", ".join(f"{name} INTEGER NOT NULL DEFAULT 0" for name in _COUNTERS)
        conn.execute(f"""CREATE TABLE IF NOT EXISTS mcpstat_usage (
            server TEXT NOT NULL DEFAULT '', type TEXT NOT NULL DEFAULT 'tool',
            name TEXT NOT NULL, {counters}, last_accessed TEXT, created_at TEXT,
            min_duration_ms INTEGER, max_duration_ms INTEGER,
            latency_complete INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY(server, type, name))""")
        conn.execute("""CREATE TABLE IF NOT EXISTS mcpstat_metadata (
            server TEXT NOT NULL, type TEXT NOT NULL, name TEXT NOT NULL,
            tags TEXT NOT NULL DEFAULT '[]', short_description TEXT NOT NULL DEFAULT '',
            full_description TEXT NOT NULL DEFAULT '', schema_version INTEGER NOT NULL DEFAULT 4,
            updated_at TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY(server, type, name))""")
        if migrate:
            for row in conn.execute("SELECT * FROM mcpstat_usage_previous").fetchall():
                old = dict(row)
                values = {
                    k: old[k]
                    for k in (
                        *_COUNTERS,
                        "last_accessed",
                        "created_at",
                        "min_duration_ms",
                        "max_duration_ms",
                    )
                    if k in old
                }
                values.update(server=self.server_name, type=old["type"], name=old["name"])
                values["latency_complete"] = int(old.get("min_duration_ms") is None)
                names = ",".join(values)
                marks = ",".join("?" for _ in values)
                conn.execute(
                    f"INSERT INTO mcpstat_usage ({names}) VALUES ({marks})",  # nosec B608
                    tuple(values.values()),
                )
            for row in conn.execute("SELECT * FROM mcpstat_metadata_previous").fetchall():
                old = dict(row)
                usage = conn.execute(
                    "SELECT type FROM mcpstat_usage WHERE server=? AND name=?",
                    (self.server_name, old["name"]),
                ).fetchone()
                self._metadata(
                    conn,
                    old["name"],
                    usage[0] if usage else "tool",
                    [t.strip() for t in (old.get("tags") or "").split(",") if t.strip()],
                    old.get("short_description") or "",
                    old.get("full_description") or "",
                )
            conn.execute("DROP TABLE mcpstat_usage_previous")
            conn.execute("DROP TABLE mcpstat_metadata_previous")
        conn.execute("PRAGMA user_version=4")

    @_worker
    def record(
        self,
        name: str,
        primitive_type: str = "tool",
        *,
        response_chars: int | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        duration_ms: int | None = None,
        outcome: str = "success",
    ) -> None:
        """Record a primitive invocation with optional token and latency tracking.

        Uses INSERT ... ON CONFLICT for atomic upsert.

        Args:
            name: Name of the tool/prompt/resource
            primitive_type: MCP primitive type
            response_chars: Size of response in characters (for token estimation)
            input_tokens: Actual input token count (from LLM provider)
            output_tokens: Actual output token count (from LLM provider)
            duration_ms: Execution duration in milliseconds
        """
        _identity(name, primitive_type)
        if outcome not in {"success", "error", "cancelled", "incomplete"}:
            raise ValueError("Invalid outcome")
        for value in (response_chars, input_tokens, output_tokens):
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise ValueError("Usage measurements must be nonnegative integers")
        duration = duration_ms if duration_ms is not None and duration_ms >= 0 else None
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        values = dict.fromkeys(_COUNTERS, 0)
        values.update(
            call_count=1,
            total_input_tokens=input_tokens or 0,
            total_output_tokens=output_tokens or 0,
            total_response_chars=response_chars or 0,
            estimated_tokens=max(1, int(response_chars / CHARS_PER_TOKEN)) if response_chars else 0,
            total_duration_ms=duration or 0,
            duration_sample_count=int(duration is not None),
        )
        values[f"{outcome}_count"] = 1
        names = ",".join(values)
        marks = ",".join("?" for _ in values)
        updates = ",".join(f"{k}={k}+excluded.{k}" for k in values)
        # SQL identifiers are fixed counter names; all measurements are bound parameters.
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO mcpstat_usage "  # nosec B608
                f"""(server,type,name,last_accessed,created_at,min_duration_ms,max_duration_ms,{names})
                VALUES (?,?,?,?,?,?,?,{marks}) ON CONFLICT(server,type,name) DO UPDATE SET
                {updates}, last_accessed=excluded.last_accessed,
                min_duration_ms=CASE WHEN excluded.min_duration_ms IS NULL THEN min_duration_ms
                  WHEN min_duration_ms IS NULL THEN excluded.min_duration_ms ELSE MIN(min_duration_ms,excluded.min_duration_ms) END,
                max_duration_ms=CASE WHEN excluded.max_duration_ms IS NULL THEN max_duration_ms
                  WHEN max_duration_ms IS NULL THEN excluded.max_duration_ms ELSE MAX(max_duration_ms,excluded.max_duration_ms) END
                """,
                (
                    self.server_name,
                    primitive_type,
                    name,
                    now,
                    now,
                    duration,
                    duration,
                    *values.values(),
                ),
            )

    @_worker
    def report_tokens(
        self, name: str, input_tokens: int, output_tokens: int, primitive_type: str = "tool"
    ) -> None:
        """Report token usage for an existing record.

        Use this when you have actual token counts from the LLM provider
        and want to add them to an existing usage record.

        Args:
            name: Name of the tool/prompt/resource
            input_tokens: Input token count from LLM provider
            output_tokens: Output token count from LLM provider
        """
        _identity(name, primitive_type)
        if any(
            isinstance(v, bool) or not isinstance(v, int) or v < 0
            for v in (input_tokens, output_tokens)
        ):
            raise ValueError("Token counts must be nonnegative integers")
        with self._connect() as conn:
            cursor = conn.execute(
                """UPDATE mcpstat_usage SET total_input_tokens=total_input_tokens+?,
                total_output_tokens=total_output_tokens+? WHERE server=? AND type=? AND name=?""",
                (input_tokens, output_tokens, self.server_name, primitive_type, name),
            )
            if not cursor.rowcount:
                raise ValueError("Record an invocation before reporting tokens")

    def _rows(self, conn: sqlite3.Connection) -> list[dict[str, Any]]:
        rows = conn.execute(
            """WITH identities AS (
            SELECT type,name FROM mcpstat_usage WHERE server=? UNION
            SELECT type,name FROM mcpstat_metadata WHERE server=? AND active=1)
            SELECT i.type, i.name, u.*, m.tags, m.short_description, m.full_description,
                   m.active, m.updated_at, m.schema_version
            FROM identities i LEFT JOIN mcpstat_usage u ON u.server=? AND u.type=i.type AND u.name=i.name
            LEFT JOIN mcpstat_metadata m ON m.server=? AND m.type=i.type AND m.name=i.name
            ORDER BY COALESCE(u.call_count,0) DESC, u.last_accessed DESC, i.type, i.name""",
            (self.server_name,) * 4,
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            for key in _COUNTERS:
                item[key] = item.get(key) or 0
            item["tags"] = json.loads(item["tags"] or "[]")
            count = item["call_count"]
            tokens = (
                item["total_input_tokens"] + item["total_output_tokens"] or item["estimated_tokens"]
            )
            item["avg_tokens_per_call"] = tokens // count if count else 0
            samples = item["duration_sample_count"]
            item["avg_latency_ms"] = (
                (item["total_duration_ms"] // samples if samples else 0)
                if item["latency_complete"] != 0
                else None
            )
            result.append(item)
        return result

    @_worker
    def get_stats(
        self, *, include_zero: bool = True, limit: int | None = None, type_filter: str | None = None
    ) -> dict[str, Any]:
        """Get usage statistics.

        Args:
            include_zero: Include items with zero calls
            limit: Maximum number of results
            type_filter: Filter by primitive type

        Returns:
            Dictionary with stats, totals, and metadata
        """
        cap = _limit(limit)
        if not isinstance(include_zero, bool):
            raise ValueError("include_zero must be a boolean")
        if type_filter is not None and type_filter not in _TYPES:
            raise ValueError("Invalid type_filter")
        with self._connect() as conn:
            rows = self._rows(conn)
        rows = [
            r
            for r in rows
            if (include_zero or r["call_count"])
            and (type_filter is None or r["type"] == type_filter)
        ]
        return {
            "tracked_count": len(rows),
            "total_calls": sum(r["call_count"] for r in rows),
            "zero_count": sum(r["call_count"] == 0 for r in rows),
            "latest_access": max(
                (r["last_accessed"] for r in rows if r["last_accessed"]), default=None
            ),
            "token_summary": {
                **{
                    k: sum(r[k] for r in rows)
                    for k in ("total_input_tokens", "total_output_tokens")
                },
                "total_estimated_tokens": sum(r["estimated_tokens"] for r in rows),
                "has_actual_tokens": any(
                    r["total_input_tokens"] or r["total_output_tokens"] for r in rows
                ),
            },
            "latency_summary": {
                "total_duration_ms": sum(r["total_duration_ms"] for r in rows),
                "has_latency_data": any(r["min_duration_ms"] is not None for r in rows),
            },
            "stats": rows[:cap],
        }

    @_worker
    def get_by_type(self) -> dict[str, Any]:
        """Get usage statistics grouped by MCP primitive type.

        Returns:
            Dictionary with by_type grouping and summary
        """
        with self._connect() as conn:
            rows = self._rows(conn)
        grouped = {kind: [r for r in rows if r["type"] == kind] for kind in sorted(_TYPES)}
        return {
            "by_type": grouped,
            "summary": {
                kind: {"count": len(items), "total_calls": sum(r["call_count"] for r in items)}
                for kind, items in grouped.items()
                if items
            },
            "total_calls": sum(r["call_count"] for r in rows),
            "total_items": len(rows),
        }

    def _metadata(
        self,
        conn: sqlite3.Connection,
        name: str,
        primitive_type: str,
        tags: list[str],
        short: str,
        full: str,
    ) -> None:
        _identity(name, primitive_type)
        conn.execute(
            """INSERT INTO mcpstat_metadata
            (server,type,name,tags,short_description,full_description,updated_at)
            VALUES (?,?,?,?,?,?,?) ON CONFLICT(server,type,name) DO UPDATE SET
            tags=excluded.tags,short_description=excluded.short_description,
            full_description=excluded.full_description,updated_at=excluded.updated_at,active=1""",
            (
                self.server_name,
                primitive_type,
                name,
                json.dumps(tags),
                short,
                full,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )

    @_worker
    def update_metadata(
        self,
        name: str,
        *,
        tags: list[str],
        short_description: str,
        full_description: str | None = None,
        primitive_type: str = "tool",
    ) -> None:
        """Update or insert metadata for a primitive.

        Args:
            name: Primitive name
            tags: List of tags
            short_description: Brief description
            full_description: Full description
        """
        with self._connect() as conn:
            self._metadata(
                conn, name, primitive_type, tags, short_description, full_description or ""
            )

    @_worker
    def sync_metadata(
        self,
        tools: list[dict[str, Any]],
        *,
        cleanup_orphans: bool = True,
        primitive_type: str = "tool",
    ) -> None:
        """Synchronize metadata table with registered tools.

        Args:
            tools: List of tool dicts with name, description, tags, short_description
            cleanup_orphans: Deactivate unregistered tools while retaining usage
        """
        if primitive_type not in _TYPES:
            raise ValueError("Invalid primitive_type")
        with self._connect() as conn:
            if cleanup_orphans:
                conn.execute(
                    "UPDATE mcpstat_metadata SET active=0 WHERE server=? AND type=?",
                    (self.server_name, primitive_type),
                )
            for tool in tools:
                self._metadata(
                    conn,
                    tool["name"],
                    primitive_type,
                    tool.get("tags", []),
                    tool.get("short_description", ""),
                    tool.get("description", ""),
                )

    @_worker
    def get_catalog(
        self,
        *,
        tags: list[str] | None = None,
        query: str | None = None,
        include_usage: bool = True,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Get tool catalog with filtering.

        Args:
            tags: Filter by tags (must have all)
            query: Text search
            include_usage: Include usage stats
            limit: Maximum results

        Returns:
            Catalog dictionary with results and metadata
        """
        cap = _limit(limit)
        if not isinstance(include_usage, bool):
            raise ValueError("include_usage must be a boolean")
        if query is not None and (not isinstance(query, str) or len(query) > 1024):
            raise ValueError("query must be a string of at most 1024 characters")
        if tags is not None and (
            not isinstance(tags, list)
            or len(tags) > 50
            or any(not isinstance(t, str) or len(t) > 100 for t in tags)
        ):
            raise ValueError("tags must contain at most 50 strings of at most 100 characters")
        filters = [t.lower().strip() for t in tags or [] if t]
        text = " ".join((query or "").split()).lower()
        with self._connect() as conn:
            rows = [r for r in self._rows(conn) if r["active"] == 1 and r["type"] == "tool"]
        matches = [
            {
                k: r[k]
                for k in (
                    "name",
                    "tags",
                    "short_description",
                    "full_description",
                    "schema_version",
                    "updated_at",
                    "call_count",
                    "last_accessed",
                )
            }
            for r in rows
            if all(t in r["tags"] for t in filters)
            and (
                not text
                or text
                in " ".join(
                    [
                        r["name"],
                        *r["tags"],
                        r["short_description"] or "",
                        r["full_description"] or "",
                    ]
                ).lower()
            )
        ]
        if not include_usage:
            for row in matches:
                row["call_count"] = row["last_accessed"] = None
        return {
            "total_tracked": len(rows),
            "matched": len(matches),
            "all_tags": sorted({t for r in rows for t in r["tags"]}),
            "filters": {"tags": filters, "query": text or None},
            "include_usage": include_usage,
            "limit": limit,
            "total_calls": sum(r["call_count"] for r in rows) if include_usage else None,
            "results": matches[:cap],
        }
