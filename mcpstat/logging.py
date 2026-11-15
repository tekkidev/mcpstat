"""
mcpstat - Usage tracking and analytics for MCP servers.
https://github.com/tekkidev/mcpstat

Copyright (c) 2026 Vadim Bakhrenkov
SPDX-License-Identifier: MIT

File-based invocation logging for mcpstat.

Provides optional logging with no file I/O when disabled. Python's logging handlers
serialize writes. JSON encoding escapes embedded newlines and delimiters.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path


class MCPStatLogger:
    """Optional file-based logger for MCP usage and diagnostic history.

    Log format:
        One JSON object per line with timestamp, type, name, and outcome.

    Example output:
        {"timestamp":"2026-01-01T10:30:45+00:00","type":"tool","name":"convert","outcome":"success"}

    Ownership:
        Each instance owns its handler; closing it cannot affect another tracker.
        Handler writes use Python's logging locks. Close after active callers finish.

    Disabled logging:
        With log_path=None, calls are no-ops and no file is opened.

    Error messages are intentionally excluded because they can contain secrets.
    Each file rotates at 5 MiB with three backups. Give independent trackers
    separate paths so each rotating handler owns its files.
    """

    def __init__(self, log_path: str | None = None, *, logger_name: str = "mcpstat.usage") -> None:
        """Initialize file logging and create parent directories when needed.

        Args:
            log_path: Output file, or None to disable logging.
            logger_name: Name of this instance's independent logger.
        """
        self.log_path = log_path
        self._logger = logging.Logger(logger_name, logging.INFO)
        self._handler: RotatingFileHandler | None = None
        if log_path:
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            self._handler = RotatingFileHandler(
                log_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
            )
            self._handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(self._handler)

    @property
    def enabled(self) -> bool:
        """Whether logging is enabled."""
        return self._handler is not None

    def log(
        self,
        name: str,
        primitive_type: str,
        *,
        success: bool = True,
        error_msg: str | None = None,
        outcome: str | None = None,
    ) -> None:
        """Log a usage event.

        Args:
            name: Tool/prompt/resource name
            primitive_type: MCP primitive type
            success: Whether invocation succeeded
            error_msg: Accepted but omitted from logs to avoid secret exposure

        Note:
            No-op if logging is disabled - safe to call unconditionally.
        """
        del error_msg
        if self.enabled:
            self._logger.info(
                json.dumps(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "type": primitive_type,
                        "name": name[:2048],
                        "outcome": outcome or ("success" if success else "error"),
                    },
                    ensure_ascii=True,
                )
            )

    def close(self) -> None:
        """Close all handlers and release resources.

        Safe to call multiple times. Should be called during shutdown.
        """
        if self._handler is not None:
            self._logger.removeHandler(self._handler)
            self._handler.close()
            self._handler = None
