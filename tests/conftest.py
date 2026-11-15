"""
mcpstat - Usage tracking and analytics for MCP servers.
https://github.com/tekkidev/mcpstat

Copyright (c) 2026 Vadim Bakhrenkov
SPDX-License-Identifier: MIT

Pytest configuration and fixtures.
"""

from __future__ import annotations

import runpy
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


@pytest.fixture(autouse=True)
def isolate_server(monkeypatch, tmp_path):
    """Keep server tests isolated from user configuration and persistent data."""
    from mcpstat import BuiltinToolsHandler, MCPStat, server

    monkeypatch.delenv("MCPSTAT_DB_PATH", raising=False)
    monkeypatch.delenv("MCPSTAT_LOG_PATH", raising=False)
    tracker = MCPStat(
        "mcpstat",
        db_path=str(tmp_path / "server.sqlite"),
        metadata_presets=server.stat.metadata_presets,
    )
    monkeypatch.setattr(server.stat, "_db", tracker._db)
    monkeypatch.setattr(server.stat, "_logger", tracker._logger)
    monkeypatch.setattr(server, "stats_handler", BuiltinToolsHandler(tracker))
    yield
    tracker.close()


def pytest_configure(config):
    """Prepare package resources and isolate configuration before collection."""
    runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "build_package.py"), run_name="__main__"
    )
    directory = tempfile.TemporaryDirectory()
    patch = pytest.MonkeyPatch()
    patch.setenv("MCPSTAT_DB_PATH", str(Path(directory.name) / "collection.sqlite"))
    patch.setenv("MCPSTAT_LOG_ENABLED", "false")
    patch.delenv("MCPSTAT_LOG_PATH", raising=False)
    config._mcpstat_test_environment = (directory, patch)


def pytest_unconfigure(config):
    environment = getattr(config, "_mcpstat_test_environment", None)
    if environment:
        directory, patch = environment
        patch.undo()
        directory.cleanup()
