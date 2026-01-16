"""
MCPStat - Usage tracking and analytics for MCP servers.
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
SCHEMA_VERSION = 1


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

    def _ensure_schema(self) -> None:
        """Create database schema if not exists.

        Idempotent - safe to call multiple times.
        Called automatically before first operation.
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
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
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

            conn.commit()

        self._initialized = True

    async def record(
        self,
        name: str,
        primitive_type: Literal['tool', 'prompt', 'resource'] = "tool",
    ) -> None:
        """Record a primitive invocation.

        Uses INSERT ... ON CONFLICT for atomic upsert.

        Args:
            name: Name of the tool/prompt/resource
            primitive_type: MCP primitive type
        """
        self._ensure_schema()
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")

        async with self._get_lock():
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO mcpstat_usage (name, type, call_count, last_accessed, created_at)
                    VALUES (?, ?, 1, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        call_count = call_count + 1,
                        last_accessed = excluded.last_accessed,
                        type = excluded.type
                    """,
                    (name, primitive_type, now, now),
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

                query = f"""
                    SELECT u.name, u.type, u.call_count, u.last_accessed,
                           m.tags, m.short_description, m.full_description
                    FROM mcpstat_usage u
                    LEFT JOIN mcpstat_metadata m ON u.name = m.name
                    {where}
                    ORDER BY u.call_count DESC, u.last_accessed DESC
                """

                if limit:
                    query += " LIMIT ?"
                    params.append(limit)

                rows = conn.execute(query, params).fetchall()

        # Build result
        stats: list[dict[str, Any]] = []
        total_calls = 0
        zero_count = 0

        for row in rows:
            count = row["call_count"] or 0
            total_calls += count
            if count == 0:
                zero_count += 1

            stats.append({
                "name": row["name"],
                "type": row["type"],
                "call_count": count,
                "last_accessed": row["last_accessed"],
                "tags": parse_tags_string(row["tags"]),
                "short_description": row["short_description"],
                "full_description": row["full_description"],
            })

        latest = max((s["last_accessed"] for s in stats if s["last_accessed"]), default=None)

        return {
            "tracked_count": len(stats),
            "total_calls": total_calls,
            "zero_count": zero_count,
            "latest_access": latest,
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
                    (name, tags_to_string(tags), short_description, full_description or "", SCHEMA_VERSION, now),
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
                        placeholders = ",".join("?" * len(orphans))
                        conn.execute(f"DELETE FROM mcpstat_metadata WHERE name IN ({placeholders})", tuple(orphans))
                        conn.execute(
                            f"DELETE FROM mcpstat_usage WHERE name IN ({placeholders}) AND type='tool'",
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
                haystack = " ".join([
                    entry["name"],
                    " ".join(entry["tags"]),
                    entry["short_description"] or "",
                    entry["full_description"] or "",
                ]).lower()
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
