"""
mcpstat - Usage tracking and analytics for MCP servers.
https://github.com/tekkidev/mcpstat

Copyright (c) 2026 Vadim Bakhrenkov
SPDX-License-Identifier: MIT

Pytest configuration and fixtures.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from mcpstat import MCPStat, MCPStatDatabase


@pytest.fixture
def tmp_db_path():
    """Create a temporary database path."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield str(Path(tmp_dir) / "test.sqlite")


@pytest.fixture
def tmp_log_path():
    """Create a temporary log file path."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield str(Path(tmp_dir) / "test.log")


@pytest.fixture
def db(tmp_db_path: str) -> MCPStatDatabase:
    """Create a temporary MCPStatDatabase instance."""
    from mcpstat import MCPStatDatabase

    return MCPStatDatabase(tmp_db_path)


@pytest.fixture
def stat(tmp_db_path: str) -> MCPStat:
    """Create a temporary MCPStat instance."""
    from mcpstat import MCPStat

    instance = MCPStat("test-server", db_path=tmp_db_path, log_enabled=False)
    yield instance
    instance.close()
