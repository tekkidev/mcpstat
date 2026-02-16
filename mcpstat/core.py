"""
mcpstat - Usage tracking and analytics for MCP servers.
https://github.com/tekkidev/mcpstat

Copyright (c) 2026 Vadim Bakhrenkov
SPDX-License-Identifier: MIT

Core MCPStat class - the main entry point for mcpstat.

Provides a simple, unified API for usage tracking and analytics.
All configuration is passed at initialization time.
"""

from __future__ import annotations

import contextlib
import functools
import os
import sys
import time
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from mcpstat.database import MCPStatDatabase
from mcpstat.logging import MCPStatLogger
from mcpstat.utils import derive_short_description, normalize_tags

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable
    from typing import Literal, ParamSpec, TypeVar

    P = ParamSpec("P")
    T = TypeVar("T")

# Default paths - descriptive names for discoverability
DEFAULT_DB_PATH = "./mcp_stat_data.sqlite"
DEFAULT_LOG_PATH = "./mcp_stat.log"


class MCPStat:
    """Main statistics tracking class for MCP servers.

    Provides a unified API for:
    - Recording tool/prompt/resource invocations
    - Querying usage statistics
    - Managing tool metadata
    - Optional file-based audit logging

    All configuration is passed at initialization - no config files needed.
    Environment variables can override defaults.

    Example:
        ```python
        from mcpstat import MCPStat

        # Basic usage
        stat = MCPStat("my-server")

        # With all options
        stat = MCPStat(
            server_name="my-server",
            db_path="./stats.sqlite",
            log_path="./usage.log",
            log_enabled=True,
            metadata_presets={
                "my_tool": {"tags": ["api"], "short": "My description"}
            }
        )

        # In your tool handler
        @app.call_tool()
        async def handle_tool(name: str, arguments: dict):
            await stat.record(name, "tool")
            # ... your logic
        ```

    Environment Variables:
        MCPSTAT_DB_PATH: Override db_path
        MCPSTAT_LOG_PATH: Override log_path
        MCPSTAT_LOG_ENABLED: Override log_enabled (true/1/yes)

    Thread Safety:
        All async methods are thread-safe via asyncio.Lock in database layer.
    """

    __slots__ = (
        "_db",
        "_logger",
        "_tools_cache",
        "cleanup_orphans",
        "db_path",
        "log_enabled",
        "log_path",
        "metadata_presets",
        "server_name",
    )

    def __init__(
        self,
        server_name: str,
        *,
        db_path: str | None = None,
        log_path: str | None = None,
        log_enabled: bool | None = None,
        metadata_presets: dict[str, dict[str, Any]] | None = None,
        cleanup_orphans: bool = True,
    ) -> None:
        """Initialize MCP statistics tracking.

        Args:
            server_name: Server identifier (used in prompts/descriptions)
            db_path: Path to SQLite database (default: ./mcp_stat_data.sqlite)
            log_path: Path to log file (default: ./mcp_stat.log)
            log_enabled: Enable file logging (default: False, or env var)
            metadata_presets: Pre-defined tool metadata {name: {tags, short}}
            cleanup_orphans: Auto-remove metadata for unregistered tools

        Environment Variable Overrides:
            MCPSTAT_DB_PATH: Override db_path
            MCPSTAT_LOG_PATH: Override log_path
            MCPSTAT_LOG_ENABLED: Override log_enabled
        """
        self.server_name = server_name
        self.cleanup_orphans = cleanup_orphans
        self.metadata_presets = metadata_presets or {}
        self._tools_cache: list[Any] | None = None

        # Resolve paths with env var overrides
        self.db_path = os.getenv("MCPSTAT_DB_PATH", db_path or DEFAULT_DB_PATH)
        self.log_path = os.getenv("MCPSTAT_LOG_PATH", log_path or DEFAULT_LOG_PATH)

        # Resolve log_enabled with env var override
        env_log = os.getenv("MCPSTAT_LOG_ENABLED", "").lower()
        if env_log in ("true", "1", "yes"):
            self.log_enabled = True
        elif env_log in ("false", "0", "no"):
            self.log_enabled = False
        else:
            self.log_enabled = log_enabled if log_enabled is not None else False

        # Initialize components
        self._db = MCPStatDatabase(self.db_path)
        self._logger = MCPStatLogger(self.log_path if self.log_enabled else None)

    async def record(
        self,
        name: str,
        primitive_type: Literal["tool", "prompt", "resource"] = "tool",
        *,
        success: bool = True,
        error_msg: str | None = None,
        response_chars: int | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        duration_ms: int | None = None,
    ) -> None:
        """Record a tool/prompt/resource invocation.

        Call this at the START of handlers to guarantee 100% coverage.
        Optionally pass response size, token counts, or duration for analytics.

        Args:
            name: Name of the primitive being invoked
            primitive_type: Type of MCP primitive
            success: Whether invocation succeeded
            error_msg: Error message for failures (logged only)
            response_chars: Response size in characters (for token estimation)
            input_tokens: Actual input token count (if known from LLM API)
            output_tokens: Actual output token count (if known from LLM API)
            duration_ms: Execution duration in milliseconds

        Example:
            ```python
            @app.call_tool()
            async def handle_tool(name: str, arguments: dict):
                await stat.record(name, "tool")
                # ... your logic

            # With response and latency tracking
            import time
            start = time.perf_counter()
            result = my_tool_logic()
            duration_ms = int((time.perf_counter() - start) * 1000)
            await stat.record(
                name, "tool",
                response_chars=len(str(result)),
                duration_ms=duration_ms
            )
            ```
        """
        # File logging (if enabled)
        self._logger.log(name, primitive_type, success=success, error_msg=error_msg)

        # SQLite tracking
        try:
            await self._db.record(
                name,
                primitive_type,
                response_chars=response_chars,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            # Never fail the main flow due to tracking
            print(f"[mcpstat] SQLite tracking failed for {name}: {exc}", file=sys.stderr)

    async def report_tokens(
        self,
        name: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Report token usage for a previously recorded call.

        Use this when actual token counts are available after the fact
        (e.g., from LLM API response). This increments the cumulative
        token counters without incrementing call_count.

        Args:
            name: Name of the tool/prompt/resource
            input_tokens: Input token count from LLM API
            output_tokens: Output token count from LLM API

        Example:
            ```python
            # In your client code after LLM call
            response = await anthropic.messages.create(...)
            await stat.report_tokens(
                tool_name,
                response.usage.input_tokens,
                response.usage.output_tokens
            )
            ```
        """
        try:
            await self._db.report_tokens(name, input_tokens, output_tokens)
        except Exception as exc:
            print(f"[mcpstat] Token reporting failed for {name}: {exc}", file=sys.stderr)

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
            limit: Maximum results
            type_filter: Filter by type (tool/prompt/resource)

        Returns:
            Usage statistics dictionary with stats list
        """
        return await self._db.get_stats(
            include_zero=include_zero,
            limit=limit,
            type_filter=type_filter,
        )

    async def get_by_type(self) -> dict[str, Any]:
        """Get usage statistics grouped by MCP primitive type.

        Returns:
            Dictionary with by_type grouping and summary
        """
        return await self._db.get_by_type()

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
            Catalog dictionary with results
        """
        return await self._db.get_catalog(
            tags=tags,
            query=query,
            include_usage=include_usage,
            limit=limit,
        )

    async def sync_tools(self, tools: list[Any]) -> None:
        """Synchronize tool metadata from MCP Tool objects.

        Extracts metadata from Tool objects, applies presets,
        and syncs with database.

        Args:
            tools: List of MCP Tool objects (with .name, .description)
        """
        tool_dicts = []

        for tool in tools:
            name = tool.name
            description = getattr(tool, "description", None)

            # Check for preset metadata
            preset = self.metadata_presets.get(name, {})

            if preset:
                tags = normalize_tags(preset.get("tags", []))
                short = (
                    preset.get("short")
                    or preset.get("short_description")
                    or derive_short_description(description, name)
                )
            else:
                # Generate tags from name (filter stopwords for auto-generated)
                generated = name.replace("-", " ").replace("_", " ").split()
                tags = normalize_tags([name, *generated], filter_stopwords=True)
                short = derive_short_description(description, name)

            if not tags:
                tags = [name.lower()]

            tool_dicts.append(
                {
                    "name": name,
                    "description": description or "",
                    "tags": tags,
                    "short_description": short,
                }
            )

        await self._db.sync_metadata(tool_dicts, cleanup_orphans=self.cleanup_orphans)
        self._tools_cache = tools

    async def sync_prompts(self, prompts: list[Any]) -> None:
        """Synchronize prompt metadata from MCP Prompt objects.

        Similar to sync_tools but for prompts. Extracts metadata
        and registers for tracking.

        Args:
            prompts: List of MCP Prompt objects (with .name, .description)
        """
        for prompt in prompts:
            name = prompt.name
            description = getattr(prompt, "description", None)
            preset = self.metadata_presets.get(name, {})

            if preset:
                tags = normalize_tags(preset.get("tags", []))
                short = (
                    preset.get("short")
                    or preset.get("short_description")
                    or derive_short_description(description, name)
                )
            else:
                tags = normalize_tags([name, "prompt"], filter_stopwords=True)
                short = derive_short_description(description, name)

            await self._db.update_metadata(
                name,
                tags=tags,
                short_description=short,
                full_description=description,
            )

    async def sync_resources(self, resources: list[Any]) -> None:
        """Synchronize resource metadata from MCP Resource objects.

        Similar to sync_tools but for resources.

        Args:
            resources: List of MCP Resource objects (with .name, .description)
        """
        for resource in resources:
            name = getattr(resource, "name", None) or str(getattr(resource, "uri", "unknown"))
            description = getattr(resource, "description", None)
            preset = self.metadata_presets.get(name, {})

            if preset:
                tags = normalize_tags(preset.get("tags", []))
                short = preset.get("short") or derive_short_description(description, name)
            else:
                tags = normalize_tags([name, "resource"], filter_stopwords=True)
                short = derive_short_description(description, name)

            await self._db.update_metadata(
                name,
                tags=tags,
                short_description=short,
                full_description=description,
            )

    async def register_metadata(
        self,
        name: str,
        *,
        tags: list[str],
        short_description: str,
        full_description: str | None = None,
    ) -> None:
        """Manually register metadata for a primitive.

        Useful for non-standard primitives or custom tracking.

        Args:
            name: Primitive name
            tags: List of tags
            short_description: Brief description
            full_description: Full description
        """
        await self._db.update_metadata(
            name,
            tags=normalize_tags(tags),
            short_description=short_description,
            full_description=full_description,
        )

    def add_preset(
        self,
        name: str,
        *,
        tags: list[str],
        short: str,
    ) -> None:
        """Add a metadata preset for future sync operations.

        Args:
            name: Tool name
            tags: List of tags
            short: Short description
        """
        self.metadata_presets[name] = {"tags": tags, "short": short}

    def track(
        self,
        func: Callable[P, Awaitable[T]] | None = None,
        *,
        primitive_type: Literal["tool", "prompt", "resource"] = "tool",
    ) -> (
        Callable[P, Awaitable[T]] | Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]
    ):
        """Decorator that automatically tracks tool calls with latency.

        Wraps an async handler function to automatically record:
        - Call count
        - Execution time (latency)
        - Response size (optional, from return value)

        Can be used with or without parentheses:

        Example:
            ```python
            # Simple usage - tracks latency automatically
            @app.call_tool()
            @stat.track
            async def handle_tool(name: str, arguments: dict):
                return await my_logic(arguments)

            # With explicit type
            @app.call_tool()
            @stat.track(primitive_type="tool")
            async def handle_tool(name: str, arguments: dict):
                return await my_logic(arguments)
            ```

        Args:
            func: The async function to wrap (when used without parentheses)
            primitive_type: Type of MCP primitive (tool/prompt/resource)

        Returns:
            Decorated function that tracks execution
        """

        def decorator(fn: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
            @functools.wraps(fn)
            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                # Extract name from first positional arg (MCP convention)
                name = args[0] if args else kwargs.get("name", fn.__name__)
                if not isinstance(name, str):
                    name = fn.__name__

                start = time.perf_counter()
                error_msg: str | None = None
                success = True

                try:
                    result = await fn(*args, **kwargs)
                    return result
                except Exception as exc:
                    success = False
                    error_msg = str(exc)
                    raise
                finally:
                    duration_ms = int((time.perf_counter() - start) * 1000)
                    with contextlib.suppress(Exception):  # nosec B110
                        await self.record(
                            name,
                            primitive_type,
                            success=success,
                            error_msg=error_msg,
                            duration_ms=duration_ms,
                        )

            return wrapper

        # Handle both @stat.track and @stat.track() syntax
        if func is not None:
            return decorator(func)
        return decorator

    @asynccontextmanager
    async def tracking(
        self,
        name: str,
        primitive_type: Literal["tool", "prompt", "resource"] = "tool",
    ) -> AsyncIterator[None]:
        """Context manager for tracking execution with automatic latency measurement.

        Use this when you need more control than the @track decorator provides,
        or when working with code that doesn't fit the decorator pattern.

        Example:
            ```python
            async def handle_tool(name: str, arguments: dict):
                async with stat.tracking(name, "tool"):
                    result = await my_logic(arguments)
                    return result
            ```

        Args:
            name: Name of the tool/prompt/resource
            primitive_type: Type of MCP primitive

        Yields:
            None - tracking happens on context exit
        """
        start = time.perf_counter()
        error_msg: str | None = None
        success = True

        try:
            yield
        except Exception as exc:
            success = False
            error_msg = str(exc)
            raise
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            with contextlib.suppress(Exception):  # nosec B110
                await self.record(
                    name,
                    primitive_type,
                    success=success,
                    error_msg=error_msg,
                    duration_ms=duration_ms,
                )

    def close(self) -> None:
        """Release resources.

        Call during server shutdown for clean resource release.
        """
        self._logger.close()
