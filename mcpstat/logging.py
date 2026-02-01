"""
mcpstat - Usage tracking and analytics for MCP servers.
https://github.com/tekkidev/mcpstat

Copyright (c) 2026 Vadim Bakhrenkov
SPDX-License-Identifier: MIT

File-based audit logging for mcpstat.

Provides optional file logging with minimal overhead when disabled.
Thread-safe via Python's logging module.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Literal


class MCPStatLogger:
    """Optional file-based audit logger for MCP usage.

    Provides a fallback logging mechanism for debugging and auditing.
    Uses Python's standard logging module for thread safety.

    Log Format:
        YYYY-MM-DDTHH:MM:SS|type:name|status[|error_truncated]

    Example output:
        2026-01-01T10:30:45|tool:celsius_to_fahrenheit|OK
        2026-01-01T10:30:50|tool:fahrenheit_to_celsius|OK
        2026-01-01T10:31:00|tool:unknown_tool|FAIL|Unknown tool

    Thread Safety:
        All operations are thread-safe via Python's logging module.

    Performance:
        When disabled (log_path=None), operations are no-ops with
        minimal overhead (~50ns per call).
    """

    __slots__ = ("_enabled", "_logger", "log_path")

    def __init__(
        self,
        log_path: str | None = None,
        *,
        logger_name: str = "mcpstat.usage",
    ) -> None:
        """Initialize file logger.

        Args:
            log_path: Path to log file, or None to disable logging
            logger_name: Logger name for Python logging hierarchy

        Note:
            Creates parent directories if they don't exist.
        """
        self.log_path = log_path
        self._enabled = log_path is not None
        self._logger: logging.Logger | None = None

        if self._enabled and log_path:
            self._setup_logger(log_path, logger_name)

    def _setup_logger(self, log_path: str, logger_name: str) -> None:
        """Configure the file handler."""
        # Ensure directory exists
        log_path_obj = Path(log_path)
        if log_path_obj.parent.name:
            log_path_obj.parent.mkdir(parents=True, exist_ok=True)

        self._logger = logging.getLogger(logger_name)
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False  # Don't bubble to root logger

        # Avoid duplicate handlers on re-initialization
        if not self._logger.handlers:
            handler = logging.FileHandler(log_path, encoding="utf-8")
            handler.setFormatter(
                logging.Formatter("%(asctime)s|%(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
            )
            self._logger.addHandler(handler)

    @property
    def enabled(self) -> bool:
        """Whether logging is enabled."""
        return self._enabled

    def log(
        self,
        name: str,
        primitive_type: Literal["tool", "prompt", "resource"],
        *,
        success: bool = True,
        error_msg: str | None = None,
    ) -> None:
        """Log a usage event.

        Args:
            name: Tool/prompt/resource name
            primitive_type: MCP primitive type
            success: Whether invocation succeeded
            error_msg: Error message if failed (truncated to 100 chars)

        Note:
            No-op if logging is disabled - safe to call unconditionally.
        """
        if not self._enabled or self._logger is None:
            return

        status = "OK" if success else "FAIL"
        entry = f"{primitive_type}:{name}|{status}"

        if error_msg:
            # Truncate long errors to prevent log bloat
            entry += f"|{error_msg[:100]}"

        self._logger.info(entry)

    def close(self) -> None:
        """Close all handlers and release resources.

        Safe to call multiple times. Should be called during shutdown.
        """
        if self._logger:
            for handler in self._logger.handlers[:]:
                handler.close()
                self._logger.removeHandler(handler)
            self._logger = None
        self._enabled = False
