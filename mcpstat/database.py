"""
mcpstat - Usage tracking and analytics for MCP servers.
https://github.com/tekkidev/mcpstat

Copyright (c) 2026 Vadim Bakhrenkov
SPDX-License-Identifier: MIT

SQLite database management for mcpstat.

Provides schema creation, migrations, and async-safe queries.
Uses a single connection with asyncio.Lock for thread safety.
"""

from __future__ import annotations

import asyncio
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mcpstat.utils import parse_tags_string, tags_to_string

if TYPE_CHECKING:
    from collections.abc import Generator
    from typing import Literal

# Schema version for migrations
# v1: Initial schema
# v2: Added token tracking columns (total_input_tokens, total_output_tokens,
#     total_response_chars, estimated_tokens)
# v3: Added latency tracking columns (total_duration_ms, min_duration_ms,
#     max_duration_ms)
SCHEMA_VERSION = 3

# Token estimation: ~3.5 characters per token (conservative for mixed content)
CHARS_PER_TOKEN = 3.5


class MCPStatDatabase:
    """SQLite database manager for MCP usage tracking.

    Features:
    - Async-safe operations via asyncio.Lock
    - Automatic schema creation and migration
    - Atomic upsert operations
    - Orphan cleanup for removed tools

    Thread Safety:
        All async methods are protected by an asyncio.Lock.
        Sync methods (_ensure_schema) are only called during init.

    Connection Management:
        Uses a new connection per operation for simplicity and
        to avoid connection state issues in async contexts.
        SQLite's WAL mode could be enabled for better concurrency.
    """

    __slots__ = ("_initialized", "_lock", "db_path")

    def __init__(self, db_path: str) -> None:
        """Initialize database manager.

        Args:
            db_path: Path to SQLite database file

        Note:
            Schema is created lazily on first operation.
        """
        self.db_path = db_path
        self._lock: asyncio.Lock | None = None
        self._initialized = False

    def _get_lock(self) -> asyncio.Lock:
        """Get or create the asyncio lock (lazy initialization)."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database connections.

        Yields:
            SQLite connection with row_factory set
        """
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _migrate_to_v2(self, conn: sqlite3.Connection) -> None:
        """Migrate schema to v2: Add token tracking columns.

        Safe to run multiple times - checks for existing columns.
        """
        # Get existing columns in mcpstat_usage
        cursor = conn.execute("PRAGMA table_info(mcpstat_usage)")
        existing_cols = {row[1] for row in cursor.fetchall()}

        # Columns to add for token tracking
        new_columns = [
            ("total_input_tokens", "INTEGER NOT NULL DEFAULT 0"),
            ("total_output_tokens", "INTEGER NOT NULL DEFAULT 0"),
            ("total_response_chars", "INTEGER NOT NULL DEFAULT 0"),
            ("estimated_tokens", "INTEGER NOT NULL DEFAULT 0"),
        ]

        for col_name, col_def in new_columns:
            if col_name not in existing_cols:
                conn.execute(f"ALTER TABLE mcpstat_usage ADD COLUMN {col_name} {col_def}")

    def _migrate_to_v3(self, conn: sqlite3.Connection) -> None:
        """Migrate schema to v3: Add latency tracking columns.

        Safe to run multiple times - checks for existing columns.
        """
        # Get existing columns in mcpstat_usage
        cursor = conn.execute("PRAGMA table_info(mcpstat_usage)")
        existing_cols = {row[1] for row in cursor.fetchall()}

        # Columns to add for latency tracking
        new_columns = [
            ("total_duration_ms", "INTEGER NOT NULL DEFAULT 0"),
            ("min_duration_ms", "INTEGER"),  # NULL means no data yet
            ("max_duration_ms", "INTEGER"),  # NULL means no data yet
        ]

        for col_name, col_def in new_columns:
            if col_name not in existing_cols:
                conn.execute(f"ALTER TABLE mcpstat_usage ADD COLUMN {col_name} {col_def}")

    def _ensure_schema(self) -> None:
        """Create database schema if not exists.

        Idempotent - safe to call multiple times.
        Called automatically before first operation.
        Handles migrations for schema updates.
        """
        if self._initialized:
            return

        # Ensure directory exists
        db_path = Path(self.db_path)
        if db_path.parent.name:
            db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as conn:
            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode=WAL")

            # Usage tracking table - all MCP primitives
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mcpstat_usage (
                    name TEXT PRIMARY KEY,
                    type TEXT NOT NULL DEFAULT 'tool',
                    call_count INTEGER NOT NULL DEFAULT 0,
                    last_accessed TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    total_input_tokens INTEGER NOT NULL DEFAULT 0,
                    total_output_tokens INTEGER NOT NULL DEFAULT 0,
                    total_response_chars INTEGER NOT NULL DEFAULT 0,
                    estimated_tokens INTEGER NOT NULL DEFAULT 0,
                    total_duration_ms INTEGER NOT NULL DEFAULT 0,
                    min_duration_ms INTEGER,
                    max_duration_ms INTEGER
                )
            """)

            # Metadata table - enrichment data for tools
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mcpstat_metadata (
                    name TEXT PRIMARY KEY,
                    tags TEXT NOT NULL DEFAULT '',
                    short_description TEXT NOT NULL DEFAULT '',
                    full_description TEXT DEFAULT '',
                    schema_version INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL
                )
            """)

            # Indexes for common queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_mcpstat_usage_type
                ON mcpstat_usage(type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_mcpstat_usage_count
                ON mcpstat_usage(call_count DESC)
            """)

            # Run migrations for existing databases
            self._migrate_to_v2(conn)
            self._migrate_to_v3(conn)

            conn.commit()

        self._initialized = True

    async def record(
        self,
        name: str,
        primitive_type: Literal["tool", "prompt", "resource"] = "tool",
        *,
        response_chars: int | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        duration_ms: int | None = None,
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
        self._ensure_schema()
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")

        # Calculate estimated tokens from response size
        est_tokens = 0
        if response_chars is not None and response_chars > 0:
            est_tokens = max(1, int(response_chars / CHARS_PER_TOKEN))

        # Prepare duration values
        dur_ms = duration_ms if duration_ms is not None and duration_ms >= 0 else None
        dur_total = dur_ms if dur_ms is not None else 0

        async with self._get_lock():
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO mcpstat_usage (
                        name, type, call_count, last_accessed, created_at,
                        total_input_tokens, total_output_tokens,
                        total_response_chars, estimated_tokens,
                        total_duration_ms, min_duration_ms, max_duration_ms
                    )
                    VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        call_count = call_count + 1,
                        last_accessed = excluded.last_accessed,
                        type = excluded.type,
                        total_input_tokens = total_input_tokens + excluded.total_input_tokens,
                        total_output_tokens = total_output_tokens + excluded.total_output_tokens,
                        total_response_chars = total_response_chars + excluded.total_response_chars,
                        estimated_tokens = estimated_tokens + excluded.estimated_tokens,
                        total_duration_ms = total_duration_ms + COALESCE(excluded.total_duration_ms, 0),
                        min_duration_ms = CASE
                            WHEN excluded.min_duration_ms IS NULL THEN min_duration_ms
                            WHEN min_duration_ms IS NULL THEN excluded.min_duration_ms
                            ELSE MIN(min_duration_ms, excluded.min_duration_ms)
                        END,
                        max_duration_ms = CASE
                            WHEN excluded.max_duration_ms IS NULL THEN max_duration_ms
                            WHEN max_duration_ms IS NULL THEN excluded.max_duration_ms
                            ELSE MAX(max_duration_ms, excluded.max_duration_ms)
                        END
                    """,
                    (
                        name,
                        primitive_type,
                        now,
                        now,
                        input_tokens or 0,
                        output_tokens or 0,
                        response_chars or 0,
                        est_tokens,
                        dur_total,
                        dur_ms,
                        dur_ms,
                    ),
                )
                conn.commit()

    async def report_tokens(
        self,
        name: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Report token usage for an existing record.

        Use this when you have actual token counts from the LLM provider
        and want to add them to an existing usage record.

        Args:
            name: Name of the tool/prompt/resource
            input_tokens: Input token count from LLM provider
            output_tokens: Output token count from LLM provider
        """
        self._ensure_schema()

        async with self._get_lock():
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE mcpstat_usage
                    SET total_input_tokens = total_input_tokens + ?,
                        total_output_tokens = total_output_tokens + ?
                    WHERE name = ?
                    """,
                    (input_tokens, output_tokens, name),
                )
                conn.commit()

    async def get_stats(
        self,
        *,
        include_zero: bool = True,
        limit: int | None = None,
        type_filter: str | None = None,
    ) -> dict[str, Any]:
        """Get usage statistics.

        Args:
            include_zero: Include items with zero calls
            limit: Maximum number of results
            type_filter: Filter by primitive type

        Returns:
            Dictionary with stats, totals, and metadata
        """
        self._ensure_schema()

        async with self._get_lock():
            with self._connect() as conn:
                # Build query
                conditions: list[str] = []
                params: list[Any] = []

                if type_filter:
                    conditions.append("u.type = ?")
                    params.append(type_filter)

                if not include_zero:
                    conditions.append("u.call_count > 0")

                where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

                # Safe: where clause constructed from enum/bool params, not user input
                query = f"""
                    SELECT u.name, u.type, u.call_count, u.last_accessed,
                           u.total_input_tokens, u.total_output_tokens,
                           u.total_response_chars, u.estimated_tokens,
                           u.total_duration_ms, u.min_duration_ms, u.max_duration_ms,
                           m.tags, m.short_description, m.full_description
                    FROM mcpstat_usage u
                    LEFT JOIN mcpstat_metadata m ON u.name = m.name
                    {where}
                    ORDER BY u.call_count DESC, u.last_accessed DESC
                """  # nosec B608

                if limit:
                    query += " LIMIT ?"
                    params.append(limit)

                rows = conn.execute(query, params).fetchall()

        # Build result
        stats: list[dict[str, Any]] = []
        total_calls = 0
        zero_count = 0
        total_input_tokens = 0
        total_output_tokens = 0
        total_estimated_tokens = 0
        total_duration_ms = 0

        for row in rows:
            count = row["call_count"] or 0
            total_calls += count
            if count == 0:
                zero_count += 1

            input_tokens = row["total_input_tokens"] or 0
            output_tokens = row["total_output_tokens"] or 0
            estimated = row["estimated_tokens"] or 0
            duration_ms = row["total_duration_ms"] or 0
            min_dur = row["min_duration_ms"]
            max_dur = row["max_duration_ms"]

            total_input_tokens += input_tokens
            total_output_tokens += output_tokens
            total_estimated_tokens += estimated
            total_duration_ms += duration_ms

            # Calculate average tokens per call
            avg_tokens = 0
            if count > 0:
                actual_total = input_tokens + output_tokens
                if actual_total > 0:
                    avg_tokens = actual_total // count
                elif estimated > 0:
                    avg_tokens = estimated // count

            # Calculate average latency per call
            avg_latency_ms = 0
            if count > 0 and duration_ms > 0:
                avg_latency_ms = duration_ms // count

            stats.append(
                {
                    "name": row["name"],
                    "type": row["type"],
                    "call_count": count,
                    "last_accessed": row["last_accessed"],
                    "tags": parse_tags_string(row["tags"]),
                    "short_description": row["short_description"],
                    "full_description": row["full_description"],
                    "total_input_tokens": input_tokens,
                    "total_output_tokens": output_tokens,
                    "total_response_chars": row["total_response_chars"] or 0,
                    "estimated_tokens": estimated,
                    "avg_tokens_per_call": avg_tokens,
                    "total_duration_ms": duration_ms,
                    "min_duration_ms": min_dur,
                    "max_duration_ms": max_dur,
                    "avg_latency_ms": avg_latency_ms,
                }
            )

        latest = max((s["last_accessed"] for s in stats if s["last_accessed"]), default=None)

        return {
            "tracked_count": len(stats),
            "total_calls": total_calls,
            "zero_count": zero_count,
            "latest_access": latest,
            "token_summary": {
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
                "total_estimated_tokens": total_estimated_tokens,
                "has_actual_tokens": total_input_tokens > 0 or total_output_tokens > 0,
            },
            "latency_summary": {
                "total_duration_ms": total_duration_ms,
                "has_latency_data": total_duration_ms > 0,
            },
            "stats": stats,
        }

    async def get_by_type(self) -> dict[str, Any]:
        """Get usage statistics grouped by MCP primitive type.

        Returns:
            Dictionary with by_type grouping and summary
        """
        self._ensure_schema()

        async with self._get_lock():
            with self._connect() as conn:
                rows = conn.execute("""
                    SELECT name, type, call_count, last_accessed
                    FROM mcpstat_usage
                    ORDER BY call_count DESC
                """).fetchall()

                summaries = conn.execute("""
                    SELECT type, COUNT(*) as count, SUM(call_count) as total
                    FROM mcpstat_usage
                    GROUP BY type
                """).fetchall()

        # Group by type
        by_type: dict[str, list[dict[str, Any]]] = {
            "tool": [],
            "resource": [],
            "prompt": [],
        }
        total_calls = 0

        for row in rows:
            entry = {
                "name": row["name"],
                "type": row["type"],
                "call_count": row["call_count"] or 0,
                "last_accessed": row["last_accessed"],
            }
            total_calls += entry["call_count"]
            ptype = row["type"] or "tool"
            by_type.setdefault(ptype, []).append(entry)

        # Build summary
        summary = {
            row["type"]: {"count": row["count"], "total_calls": row["total"] or 0}
            for row in summaries
        }

        return {
            "by_type": by_type,
            "summary": summary,
            "total_calls": total_calls,
            "total_items": len(rows),
        }

    async def update_metadata(
        self,
        name: str,
        *,
        tags: list[str],
        short_description: str,
        full_description: str | None = None,
    ) -> None:
        """Update or insert metadata for a primitive.

        Args:
            name: Primitive name
            tags: List of tags
            short_description: Brief description
            full_description: Full description
        """
        self._ensure_schema()
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")

        async with self._get_lock():
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO mcpstat_metadata
                    (name, tags, short_description, full_description, schema_version, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        tags = excluded.tags,
                        short_description = excluded.short_description,
                        full_description = excluded.full_description,
                        schema_version = excluded.schema_version,
                        updated_at = excluded.updated_at
                    """,
                    (
                        name,
                        tags_to_string(tags),
                        short_description,
                        full_description or "",
                        SCHEMA_VERSION,
                        now,
                    ),
                )
                conn.commit()

    async def sync_metadata(
        self,
        tools: list[dict[str, Any]],
        *,
        cleanup_orphans: bool = True,
    ) -> None:
        """Synchronize metadata table with registered tools.

        Args:
            tools: List of tool dicts with name, description, tags, short_description
            cleanup_orphans: Remove metadata for unregistered tools
        """
        self._ensure_schema()
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        tool_names = {t["name"] for t in tools}

        async with self._get_lock():
            with self._connect() as conn:
                # Get existing
                existing = {
                    row["name"]: row
                    for row in conn.execute(
                        "SELECT name, tags, short_description, full_description, schema_version FROM mcpstat_metadata"
                    )
                }

                for tool in tools:
                    name = tool["name"]
                    tags_str = tags_to_string(tool.get("tags", [name]))
                    short = tool.get("short_description", "")
                    full = tool.get("description", "")

                    if name not in existing:
                        conn.execute(
                            """
                            INSERT INTO mcpstat_metadata
                            (name, tags, short_description, full_description, schema_version, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (name, tags_str, short, full, SCHEMA_VERSION, now),
                        )
                    else:
                        current = existing[name]
                        if (
                            current["tags"] != tags_str
                            or current["short_description"] != short
                            or current["full_description"] != full
                            or (current["schema_version"] or 0) != SCHEMA_VERSION
                        ):
                            conn.execute(
                                """
                                UPDATE mcpstat_metadata
                                SET tags=?, short_description=?, full_description=?, schema_version=?, updated_at=?
                                WHERE name=?
                                """,
                                (tags_str, short, full, SCHEMA_VERSION, now, name),
                            )

                # Cleanup orphans
                if cleanup_orphans:
                    orphans = set(existing.keys()) - tool_names
                    if orphans:
                        # Safe: placeholders are ? markers, values passed via tuple
                        placeholders = ",".join("?" * len(orphans))
                        conn.execute(
                            f"DELETE FROM mcpstat_metadata WHERE name IN ({placeholders})",  # nosec B608
                            tuple(orphans),
                        )
                        conn.execute(
                            f"DELETE FROM mcpstat_usage WHERE name IN ({placeholders}) AND type='tool'",  # nosec B608
                            tuple(orphans),
                        )

                conn.commit()

    async def get_catalog(
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
        self._ensure_schema()

        async with self._get_lock():
            with self._connect() as conn:
                rows = conn.execute("""
                    SELECT m.name, m.tags, m.short_description, m.full_description,
                           m.updated_at, m.schema_version,
                           u.call_count, u.last_accessed
                    FROM mcpstat_metadata m
                    LEFT JOIN mcpstat_usage u ON m.name = u.name
                """).fetchall()

        # Filter and build results
        results: list[dict[str, Any]] = []
        all_tags: set[str] = set()
        total_calls = 0

        tag_filters = [t.lower().strip() for t in (tags or []) if t]
        query_text = " ".join((query or "").split()).lower()

        for row in rows:
            tags_list = parse_tags_string(row["tags"])
            all_tags.update(tags_list)

            count = row["call_count"] or 0
            total_calls += count

            entry = {
                "name": row["name"],
                "short_description": row["short_description"],
                "full_description": row["full_description"],
                "tags": tags_list,
                "schema_version": row["schema_version"] or 0,
                "updated_at": row["updated_at"],
                "call_count": count if include_usage else None,
                "last_accessed": row["last_accessed"] if include_usage else None,
            }

            # Tag filter
            if tag_filters and not all(t in tags_list for t in tag_filters):
                continue

            # Text search
            if query_text:
                haystack = " ".join(
                    [
                        entry["name"],
                        " ".join(entry["tags"]),
                        entry["short_description"] or "",
                        entry["full_description"] or "",
                    ]
                ).lower()
                if query_text not in haystack:
                    continue

            results.append(entry)

        # Sort
        results.sort(key=lambda x: x["name"])
        results.sort(key=lambda x: x["last_accessed"] or "", reverse=True)
        results.sort(key=lambda x: x["call_count"] or 0, reverse=True)

        if limit and limit > 0:
            results = results[:limit]

        return {
            "total_tracked": len(rows),
            "matched": len(results),
            "all_tags": sorted(all_tags),
            "filters": {"tags": tag_filters, "query": query_text or None},
            "include_usage": include_usage,
            "limit": limit,
            "total_calls": total_calls if include_usage else None,
            "results": results,
        }
