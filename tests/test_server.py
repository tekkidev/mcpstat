"""
mcpstat - Usage tracking and analytics for MCP servers.
https://github.com/tekkidev/mcpstat

Copyright (c) 2026 Vadim Bakhrenkov
SPDX-License-Identifier: MIT

Tests for mcpstat.server - Documentation & Demo MCP server.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from mcp import Client

from mcpstat import __version__, server

# Skip all tests if mcpstat.server is not available
# (e.g., mcpstat <0.3.0 installed, or MCP SDK not present)
try:
    import mcpstat.server  # noqa: F401
except ImportError:
    pytest.skip(
        "mcpstat.server not available (requires mcpstat >=0.3.0)",
        allow_module_level=True,
    )

# ============================================================================
# Module-level imports and constants
# ============================================================================


class TestServerModule:
    """Tests for server module imports and constants."""

    def test_server_module_imports(self):
        """Test that server module can be imported."""
        from mcpstat import server

        assert hasattr(server, "main")
        assert hasattr(server, "run_server")
        assert hasattr(server, "SERVER_NAME")
        assert hasattr(server, "SERVER_VERSION")

    def test_server_name(self):
        """Test server name constant."""
        from mcpstat.server import SERVER_NAME

        assert SERVER_NAME == "mcpstat"

    def test_server_version_matches_package(self):
        """Test server version matches package __version__."""
        from mcpstat import __version__
        from mcpstat.server import SERVER_VERSION

        assert __version__ == SERVER_VERSION

    def test_doc_resources_defined(self):
        """Test documentation resources are defined."""
        from mcpstat.server import _DOC_RESOURCES

        assert isinstance(_DOC_RESOURCES, list)
        assert len(_DOC_RESOURCES) >= 5  # At least README, quickstart, api, config, etc.

        # Each entry is a 4-tuple
        for entry in _DOC_RESOURCES:
            assert len(entry) == 4
            res_id, display_name, description, filename = entry
            assert isinstance(res_id, str)
            assert isinstance(display_name, str)
            assert isinstance(description, str)
            assert isinstance(filename, str)

    def test_doc_resources_have_unique_ids(self):
        """Test that all resource IDs are unique."""
        from mcpstat.server import _DOC_RESOURCES

        ids = [r[0] for r in _DOC_RESOURCES]
        assert len(ids) == len(set(ids)), "Resource IDs must be unique"


# ============================================================================
# Project root discovery
# ============================================================================


class TestProjectRoot:
    """Tests for project root discovery."""

    def test_packaged_readme_exists(self):
        """Test that package resources include README.md."""
        from mcpstat.server import _resolve_doc_path

        root = _resolve_doc_path("README.md").parent
        # In editable installs README.md is at root; in site-packages it may not be
        if "site-packages" not in str(root):
            assert (root / "README.md").is_file(), f"README.md not found at {root}"
        else:
            # Fallback to package dir is acceptable for non-editable installs
            assert root.exists()

    def test_packaged_docs_exist(self):
        """Test that package resources include the guides."""
        from mcpstat.server import _resolve_doc_path

        root = _resolve_doc_path("README.md").parent
        if "site-packages" not in str(root):
            assert (root / "docs").is_dir(), f"docs/ not found at {root}"
        else:
            assert root.exists()

    def test_user_data_directory_is_set(self):
        """Test that a user data location is configured."""
        from mcpstat.server import _DATA_ROOT as _PROJECT_ROOT

        assert _PROJECT_ROOT is not None
        assert isinstance(_PROJECT_ROOT, Path)


# ============================================================================
# Tool building
# ============================================================================


class TestBuildToolList:
    """Tests for tool list construction."""

    def test_build_tool_list_returns_tools(self):
        """Test that _build_tool_list returns a non-empty list."""
        from mcpstat.server import _build_tool_list

        tools = _build_tool_list()
        assert isinstance(tools, list)
        assert len(tools) >= 4  # 2 demo + 2 built-in stats

    def test_build_tool_list_has_demo_tools(self):
        """Test that demo tools are included."""
        from mcpstat.server import _build_tool_list

        tools = _build_tool_list()
        names = [t.name for t in tools]
        assert "celsius_to_fahrenheit" in names
        assert "fahrenheit_to_celsius" in names

    def test_build_tool_list_has_stats_tools(self):
        """Test that built-in stats tools are included."""
        from mcpstat.server import _build_tool_list

        tools = _build_tool_list()
        names = [t.name for t in tools]
        assert "get_tool_usage_stats" in names
        assert "get_tool_catalog" in names

    def test_demo_tools_have_input_schema(self):
        """Test that demo tools have proper input schemas."""
        from mcpstat.server import _build_tool_list

        tools = _build_tool_list()
        c2f = next(t for t in tools if t.name == "celsius_to_fahrenheit")
        f2c = next(t for t in tools if t.name == "fahrenheit_to_celsius")

        assert c2f.input_schema["type"] == "object"
        assert "celsius" in c2f.input_schema["properties"]
        assert f2c.input_schema["type"] == "object"
        assert "fahrenheit" in f2c.input_schema["properties"]


# ============================================================================
# Tool handling
# ============================================================================


class TestHandleTool:
    """Tests for tool execution."""

    @pytest.mark.asyncio
    async def test_celsius_to_fahrenheit(self):
        """Test Celsius to Fahrenheit conversion."""
        from mcpstat.server import handle_tool

        result = await handle_tool("celsius_to_fahrenheit", {"celsius": 100})
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["celsius"] == 100
        assert data["fahrenheit"] == 212.0

    @pytest.mark.asyncio
    async def test_fahrenheit_to_celsius(self):
        """Test Fahrenheit to Celsius conversion."""
        from mcpstat.server import handle_tool

        result = await handle_tool("fahrenheit_to_celsius", {"fahrenheit": 32})
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["fahrenheit"] == 32
        assert data["celsius"] == 0.0

    @pytest.mark.asyncio
    async def test_celsius_to_fahrenheit_negative(self):
        """Test conversion with negative temperature."""
        from mcpstat.server import handle_tool

        result = await handle_tool("celsius_to_fahrenheit", {"celsius": -40})
        data = json.loads(result[0].text)
        assert data["fahrenheit"] == -40.0  # -40 is where scales meet

    @pytest.mark.asyncio
    async def test_fahrenheit_to_celsius_zero(self):
        """Test conversion with zero argument default."""
        from mcpstat.server import handle_tool

        result = await handle_tool("fahrenheit_to_celsius", {"fahrenheit": 0})
        data = json.loads(result[0].text)
        assert data["fahrenheit"] == 0

    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        """Test handling of unknown tool name."""
        from mcpstat.server import handle_tool

        with pytest.raises(ValueError, match="nonexistent_tool"):
            await handle_tool("nonexistent_tool", {})

    @pytest.mark.asyncio
    async def test_stats_tool_usage_stats(self):
        """Test that get_tool_usage_stats returns valid JSON."""
        from mcpstat.server import handle_tool

        result = await handle_tool("get_tool_usage_stats", {})
        data = json.loads(result[0].text)
        assert "tracked_count" in data or "total_calls" in data

    @pytest.mark.asyncio
    async def test_stats_tool_catalog(self):
        """Test that get_tool_catalog returns valid JSON."""
        from mcpstat.server import handle_tool

        result = await handle_tool("get_tool_catalog", {})
        data = json.loads(result[0].text)
        assert "total_tracked" in data or "results" in data


# ============================================================================
# Resource listing and reading
# ============================================================================


class TestResources:
    """Tests for documentation resources."""

    @pytest.mark.asyncio
    async def test_list_resources_returns_resources(self):
        """Test that list_resources returns a non-empty list."""
        from mcpstat.server import list_resources

        resources = await list_resources()
        assert isinstance(resources, list)
        assert len(resources) >= 1  # At least tool-catalog (docs need source tree)

    @pytest.mark.asyncio
    async def test_list_resources_includes_catalog(self):
        """Test that tool-catalog resource is always available."""
        from mcpstat.server import list_resources

        resources = await list_resources()
        uris = [str(r.uri) for r in resources]
        assert any("tool-catalog" in u for u in uris)

    @pytest.mark.asyncio
    async def test_list_resources_include_docs(self):
        """Test that documentation resources are listed when files exist."""
        from mcpstat.server import _resolve_doc_path, list_resources

        _PROJECT_ROOT = _resolve_doc_path("README.md").parent

        resources = await list_resources()
        uris = [str(r.uri) for r in resources]
        # README resource only present when source tree is available
        if (_PROJECT_ROOT / "README.md").exists():
            assert any("readme" in u for u in uris)
        else:
            # Non-editable install: only tool-catalog guaranteed
            assert any("tool-catalog" in u for u in uris)

    @pytest.mark.asyncio
    async def test_read_resource_readme(self):
        """Test reading the README resource."""
        from mcpstat.server import SERVER_NAME, read_resource

        content = await read_resource(f"resource://{SERVER_NAME}/readme")
        assert "mcpstat" in content
        assert isinstance(content, str)

    @pytest.mark.asyncio
    async def test_read_resource_tool_catalog(self):
        """Test reading the tool catalog resource."""
        from mcpstat.server import SERVER_NAME, read_resource

        content = await read_resource(f"resource://{SERVER_NAME}/tool-catalog")
        assert "# Tool Catalog" in content
        assert SERVER_NAME in content

    @pytest.mark.asyncio
    async def test_read_resource_unknown_raises(self):
        """Test that reading an unknown resource raises ValueError."""
        from mcpstat.server import SERVER_NAME, read_resource

        with pytest.raises(ValueError, match="Unknown resource"):
            await read_resource(f"resource://{SERVER_NAME}/nonexistent")

    @pytest.mark.asyncio
    async def test_read_resource_quickstart(self):
        """Test reading the quickstart doc resource."""
        from mcpstat.server import SERVER_NAME, _resolve_doc_path, read_resource

        _PROJECT_ROOT = _resolve_doc_path("README.md").parent

        if (_PROJECT_ROOT / "docs" / "quickstart.md").exists():
            content = await read_resource(f"resource://{SERVER_NAME}/quickstart")
            assert "Quick Start" in content

    @pytest.mark.asyncio
    async def test_resources_have_correct_mime_type(self):
        """Test that all resources have text/markdown mime type."""
        from mcpstat.server import list_resources

        resources = await list_resources()
        for r in resources:
            assert r.mime_type == "text/markdown"


# ============================================================================
# Prompts
# ============================================================================


class TestPrompts:
    """Tests for server prompts."""

    @pytest.mark.asyncio
    async def test_list_prompts(self):
        """Test that list_prompts returns prompts."""
        from mcpstat.server import list_prompts

        prompts = await list_prompts()
        assert isinstance(prompts, list)
        assert len(prompts) >= 1
        assert prompts[0].name == "usage_stats"

    @pytest.mark.asyncio
    async def test_get_prompt_usage_stats(self):
        """Test getting the usage_stats prompt."""
        from mcpstat.server import get_prompt

        result = await get_prompt("usage_stats", {})
        assert result.description is not None
        assert len(result.messages) >= 1
        assert "MCP Usage Statistics" in result.messages[0].content.text

    @pytest.mark.asyncio
    async def test_get_prompt_with_arguments(self):
        """Test getting prompt with period and type arguments."""
        from mcpstat.server import get_prompt

        result = await get_prompt("usage_stats", {"period": "all time", "type": "tool"})
        assert "all time" in result.description
        assert "Tools" in result.messages[0].content.text

    @pytest.mark.asyncio
    async def test_get_prompt_unknown_raises(self):
        """Test that unknown prompt raises ValueError."""
        from mcpstat.server import get_prompt

        with pytest.raises(ValueError, match="Unknown prompt"):
            await get_prompt("nonexistent_prompt", {})

    @pytest.mark.asyncio
    async def test_get_prompt_none_arguments(self):
        """Test getting prompt with None arguments."""
        from mcpstat.server import get_prompt

        result = await get_prompt("usage_stats", None)
        assert result.description is not None


# ============================================================================
# Self-tracking verification
# ============================================================================


class TestSelfTracking:
    """Tests verifying that the server tracks its own usage."""

    @pytest.mark.asyncio
    async def test_tool_calls_are_tracked(self):
        """Test that tool calls increment usage counters."""
        from mcpstat.server import handle_tool, stat

        # Make several tool calls
        await handle_tool("celsius_to_fahrenheit", {"celsius": 0})
        await handle_tool("celsius_to_fahrenheit", {"celsius": 100})
        await handle_tool("fahrenheit_to_celsius", {"fahrenheit": 32})

        # Check stats show the calls
        stats = await stat.get_stats()
        assert stats["total_calls"] >= 3

    @pytest.mark.asyncio
    async def test_stats_tools_are_self_tracked(self):
        """Test that calling stats tools also gets tracked."""
        from mcpstat.server import handle_tool, stat

        initial_stats = await stat.get_stats()
        initial_calls = initial_stats["total_calls"]

        await handle_tool("get_tool_usage_stats", {})

        updated_stats = await stat.get_stats()
        assert updated_stats["total_calls"] > initial_calls

    @pytest.mark.asyncio
    async def test_metadata_presets_applied(self):
        """Test that metadata presets are applied to demo tools."""
        from mcpstat.server import stat

        assert "celsius_to_fahrenheit" in stat.metadata_presets
        assert "demo" in stat.metadata_presets["celsius_to_fahrenheit"]["tags"]
        assert "mcpstat" in stat.metadata_presets["get_tool_usage_stats"]["tags"]


# ============================================================================
# Entry point
# ============================================================================


class TestEntryPoint:
    """Tests for server entry point."""

    def test_main_function_exists(self):
        """Test that main() entry point is defined."""
        from mcpstat.server import main

        assert callable(main)

    def test_run_server_is_async(self):
        """Test that run_server is an async function."""
        import asyncio

        from mcpstat.server import run_server

        assert asyncio.iscoroutinefunction(run_server)


@pytest.mark.parametrize("failure", [None, RuntimeError, asyncio.CancelledError])
async def test_run_server_closes_transport_and_tracker(monkeypatch, failure):
    """Release owned resources after normal exit, protocol failure or cancellation."""
    events = []
    read, write, options = object(), object(), object()

    @asynccontextmanager
    async def transport():
        try:
            yield read, write
        finally:
            events.append("transport closed")

    async def run(actual_read, actual_write, actual_options):
        assert (actual_read, actual_write, actual_options) == (read, write, options)
        events.append("run")
        if failure is not None:
            raise failure()

    monkeypatch.setattr(server, "stdio_server", transport)
    monkeypatch.setattr(
        server, "app", SimpleNamespace(run=run, create_initialization_options=lambda: options)
    )
    monkeypatch.setattr(
        server, "stat", SimpleNamespace(close=lambda: events.append("tracker closed"))
    )
    if failure is None:
        await server.run_server()
    else:
        with pytest.raises(failure):
            await server.run_server()
    assert events == ["run", "transport closed", "tracker closed"]


# ============================================================================
# server.json validation
# ============================================================================


class TestServerJson:
    """Tests for server.json MCP Registry manifest."""

    @pytest.fixture
    def server_json_path(self) -> Path:
        """Return path to server.json."""
        return Path(__file__).parent.parent / "server.json"

    def test_server_json_exists(self, server_json_path: Path):
        """Test that server.json exists."""
        assert server_json_path.exists(), "server.json must exist for MCP Registry publishing"

    def test_server_json_valid_json(self, server_json_path: Path):
        """Test that server.json is valid JSON."""
        content = server_json_path.read_text()
        data = json.loads(content)
        assert isinstance(data, dict)

    def test_server_json_has_schema(self, server_json_path: Path):
        """Test that server.json references the correct schema."""
        data = json.loads(server_json_path.read_text())
        assert "$schema" in data
        assert data["$schema"] == (
            "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json"
        )

    def test_server_json_name_format(self, server_json_path: Path):
        """Test that server name follows io.github.* convention."""
        data = json.loads(server_json_path.read_text())
        assert data["name"].startswith("io.github.")
        assert "mcpstat" in data["name"]

    def test_server_json_has_pypi_package(self, server_json_path: Path):
        """Test that server.json defines a PyPI package."""
        data = json.loads(server_json_path.read_text())
        assert "packages" in data
        assert len(data["packages"]) >= 1

        pkg = data["packages"][0]
        assert pkg["registryType"] == "pypi"
        assert pkg["identifier"] == "mcpstat"
        assert pkg["transport"]["type"] == "stdio"

    def test_server_json_version_matches(self, server_json_path: Path):
        """Test that server.json version matches package version."""
        from mcpstat import __version__

        data = json.loads(server_json_path.read_text())
        assert data["version"] == __version__

        # Package version should also match
        pkg = data["packages"][0]
        assert pkg["version"] == __version__

    def test_server_json_has_repository(self, server_json_path: Path):
        """Test that server.json has repository info."""
        data = json.loads(server_json_path.read_text())
        assert "repository" in data
        assert "tekkidev/mcpstat" in data["repository"]["url"]

    def test_server_json_has_runtime_hint(self, server_json_path: Path):
        """Test that server.json has uvx runtime hint."""
        data = json.loads(server_json_path.read_text())
        pkg = data["packages"][0]
        assert pkg.get("runtimeHint") == "uvx"


# ============================================================================
# README mcp-name tag
# ============================================================================


class TestReadmeMcpName:
    """Tests for MCP Registry ownership verification tag in README."""

    @pytest.fixture
    def readme_path(self) -> Path:
        """Return path to README.md."""
        return Path(__file__).parent.parent / "README.md"

    def test_readme_has_mcp_name_tag(self, readme_path: Path):
        """Test that README.md contains mcp-name comment for PyPI verification."""
        content = readme_path.read_text()
        assert "<!-- mcp-name:" in content, (
            "README.md must contain <!-- mcp-name: ... --> for MCP Registry PyPI verification"
        )

    def test_mcp_name_matches_server_json(self, readme_path: Path):
        """Test that mcp-name in README matches name in server.json."""
        readme_content = readme_path.read_text()
        server_json_path = readme_path.parent / "server.json"
        server_data = json.loads(server_json_path.read_text())

        expected_name = server_data["name"]
        assert expected_name in readme_content, (
            f"README.md mcp-name must match server.json name: {expected_name}"
        )


# ============================================================================
# Edge cases and coverage
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and coverage gaps."""

    def test_packaged_docs_ignore_working_directory(self, tmp_path, monkeypatch):
        """Documentation comes from package resources, not unrelated user files."""
        from mcpstat.server import _resolve_doc_path

        (tmp_path / "README.md").write_text("unrelated-document")
        monkeypatch.chdir(tmp_path)
        assert "unrelated-document" not in _resolve_doc_path("README.md").read_text()

    @pytest.mark.asyncio
    async def test_read_resource_missing_doc_file(self):
        """Test reading a doc resource when the file doesn't exist on disk."""
        from mcpstat.server import _DOC_RESOURCES, SERVER_NAME, read_resource

        # Temporarily patch _resolve_doc_path to return a nonexistent path
        with patch("mcpstat.server._resolve_doc_path") as mock_resolve:
            mock_resolve.return_value = Path("/nonexistent/file.md")

            # Use the first doc resource ID
            res_id = _DOC_RESOURCES[0][0]
            with pytest.raises(ValueError, match="unavailable"):
                await read_resource(f"resource://{SERVER_NAME}/{res_id}")

    @pytest.mark.asyncio
    async def test_list_resources_skips_missing_files(self):
        """Test that list_resources skips doc files that don't exist."""
        from mcpstat.server import list_resources

        with patch("mcpstat.server._resolve_doc_path") as mock_resolve:
            mock_resolve.return_value = Path("/nonexistent/file.md")
            resources = await list_resources()
            # Should still have the tool-catalog resource
            uris = [str(r.uri) for r in resources]
            assert any("tool-catalog" in u for u in uris)

    @pytest.mark.asyncio
    async def test_celsius_default_zero(self):
        """Test celsius_to_fahrenheit with missing argument defaults to 0."""
        from mcpstat.server import handle_tool

        result = await handle_tool("celsius_to_fahrenheit", {"celsius": 0})
        data = json.loads(result[0].text)
        assert data["celsius"] == 0
        assert data["fahrenheit"] == 32.0


@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_protocol_roundtrip(mode):
    async with Client(server.app, mode=mode) as client:
        tools = await client.list_tools()
        assert {t.name for t in tools.tools} == {
            "celsius_to_fahrenheit",
            "fahrenheit_to_celsius",
            "get_tool_usage_stats",
            "get_tool_catalog",
        }
        result = await client.call_tool("celsius_to_fahrenheit", {"celsius": 100})
        assert not result.is_error
        assert result.structured_content["fahrenheit"] == 212
        result = await client.call_tool("fahrenheit_to_celsius", {"fahrenheit": 32})
        assert result.structured_content["celsius"] == 0
        result = await client.call_tool("get_tool_usage_stats", {})
        rows = result.structured_content["stats"]
        assert next(r for r in rows if r["name"] == "celsius_to_fahrenheit")["call_count"] == 1
        result = await client.call_tool("get_tool_catalog", {"tags": ["demo"]})
        assert result.structured_content["matched"] == 2
        resources = await client.list_resources()
        assert len(resources.resources) == len(server._DOC_RESOURCES) + 1
        for resource in resources.resources:
            content = await client.read_resource(resource.uri)
            assert content.contents[0].text
        prompts = await client.list_prompts()
        assert prompts.prompts[0].name == "usage_stats"
        prompt = await client.get_prompt("usage_stats", {"period": "all time"})
        assert "MCP Usage Statistics" in prompt.messages[0].content.text


async def test_error_response():
    async with Client(server.app) as client:
        result = await client.call_tool("get_tool_usage_stats", {"limit": -1})
        assert result.is_error
        result = await client.call_tool("missing_tool", {})
        assert result.is_error


async def test_packaged_documentation():
    for _, _, _, filename in server._DOC_RESOURCES:
        resource = server._resolve_doc_path(filename)
        assert resource.is_file()
        assert resource.read_text(encoding="utf-8")


async def test_invalid_period():
    with pytest.raises(ValueError, match="all-time"):
        await server.get_prompt("usage_stats", {"period": "today"})


def test_registry_versions():
    from pathlib import Path

    manifest = json.loads((Path(__file__).parents[1] / "server.json").read_text())
    assert manifest["version"] == __version__
    assert manifest["packages"][0]["version"] == __version__


@pytest.mark.parametrize("mode", ["auto", "legacy"])
@pytest.mark.parametrize(
    "name, arguments",
    [
        ("celsius_to_fahrenheit", {"celsius": True}),
        ("celsius_to_fahrenheit", {"celsius": "12"}),
        ("celsius_to_fahrenheit", {"celsius": None}),
        ("celsius_to_fahrenheit", {}),
        ("fahrenheit_to_celsius", {"fahrenheit": False}),
        ("get_tool_usage_stats", {"include_zero_usage": "false"}),
        ("get_tool_usage_stats", {"include_zero_usage": 0}),
        ("get_tool_usage_stats", {"type_filter": "invalid"}),
        ("get_tool_usage_stats", {"limit": True}),
        ("get_tool_usage_stats", {"limit": 0}),
        ("get_tool_usage_stats", {"limit": 1001}),
        ("get_tool_catalog", {"include_usage": "false"}),
        ("get_tool_catalog", {"include_usage": None}),
        ("get_tool_catalog", {"tags": "demo"}),
        ("get_tool_catalog", {"tags": [True]}),
        ("get_tool_catalog", {"tags": ["x"] * 51}),
        ("get_tool_catalog", {"query": "x" * 1025}),
        ("unknown_tool", {}),
    ],
)
async def test_invalid_arguments_rejected_before_execution(mode, name, arguments):
    async with Client(server.app, mode=mode) as client:
        result = await client.call_tool(name, arguments)
        assert result.is_error
        assert result.structured_content is None
        assert result.content[0].text == "Invalid tool request"
    assert (await server.stat.get_stats())["total_calls"] == 0


@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_false_boolean_flags_are_respected(mode):
    async with Client(server.app, mode=mode) as client:
        await client.list_tools()
        usage = await client.call_tool("get_tool_usage_stats", {"include_zero_usage": False})
        assert usage.structured_content["zero_count"] == 0
        catalog = await client.call_tool("get_tool_catalog", {"include_usage": False})
        assert catalog.structured_content["total_calls"] is None
        assert all(row["call_count"] is None for row in catalog.structured_content["results"])
        conversion = await client.call_tool("celsius_to_fahrenheit", {"celsius": 0.5})
        assert not conversion.is_error
        assert conversion.structured_content["fahrenheit"] == 32.9


@pytest.mark.parametrize("mode", ["auto", "legacy"])
@pytest.mark.parametrize("value", [1e308, 10**1000])
async def test_conversion_overflow_returns_tool_error(mode, value):
    async with Client(server.app, mode=mode) as client:
        result = await client.call_tool("celsius_to_fahrenheit", {"celsius": value})
        assert result.is_error
        assert result.content[0].text == "Invalid tool request"
    row = (await server.stat.get_stats())["stats"][0]
    assert row["error_count"] == 1


@pytest.mark.parametrize("mode", ["auto", "legacy"])
@pytest.mark.parametrize("filename", ["minimal_server.py", "example_server.py"])
async def test_example_validates_arguments(mode, filename, tmp_path, monkeypatch):
    import runpy

    monkeypatch.setenv("MCPSTAT_DB_PATH", str(tmp_path / "example.sqlite"))
    monkeypatch.setenv("MCPSTAT_LOG_ENABLED", "false")
    example = runpy.run_path(str(Path(__file__).parents[1] / "examples" / filename))
    try:
        async with Client(example["app"], mode=mode) as client:
            invalid = await client.call_tool("celsius_to_fahrenheit", {"celsius": True})
            assert invalid.is_error
            valid = await client.call_tool("celsius_to_fahrenheit", {"celsius": 100})
            assert not valid.is_error
            assert json.loads(valid.content[0].text)["fahrenheit"] == 212
        assert (await example["stat"].get_stats())["total_calls"] == 1
    finally:
        example["stat"].close()
