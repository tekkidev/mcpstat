"""
mcpstat - Usage tracking and analytics for MCP servers.
https://github.com/tekkidev/mcpstat

Copyright (c) 2026 Vadim Bakhrenkov
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from mcpstat import (
    BuiltinToolsHandler,
    MCPStat,
    MCPStatDatabase,
    MCPStatLogger,
    build_prompt_definition,
    build_tool_definitions,
    derive_short_description,
    generate_stats_prompt,
    normalize_tags,
)

# ============================================================================
# Utils Tests
# ============================================================================


class TestNormalizeTags:
    """Tests for normalize_tags function."""

    def test_basic(self):
        tags = ["Test", "test", "  HELLO  ", "world", ""]
        assert normalize_tags(tags) == ["test", "hello", "world"]

    def test_empty(self):
        assert normalize_tags([]) == []
        assert normalize_tags([""]) == []
        assert normalize_tags(["", "  "]) == []

    def test_preserves_order(self):
        assert normalize_tags(["b", "a", "c"]) == ["b", "a", "c"]

    def test_deduplicates(self):
        assert normalize_tags(["a", "A", "a"]) == ["a"]

    def test_stopword_filtering(self):
        """Test stopword filtering when enabled."""
        tags = ["convert", "to", "celsius", "the", "from"]
        result = normalize_tags(tags, filter_stopwords=True)
        assert result == ["convert", "celsius"]

    def test_stopword_keeps_underscored(self):
        """Stopwords with underscores are kept."""
        tags = ["to_json", "from", "the"]
        result = normalize_tags(tags, filter_stopwords=True)
        assert "to_json" in result


class TestDeriveShortDescription:
    """Tests for derive_short_description function."""

    def test_extracts_first_sentence(self):
        desc = "Get weather data. Supports multiple formats."
        assert derive_short_description(desc, "x") == "Get weather data."

    def test_truncates_long(self):
        desc = "A" * 200
        result = derive_short_description(desc, "x")
        assert len(result) <= 160
        assert result.endswith("...")

    def test_fallback_to_name(self):
        assert derive_short_description(None, "my_cool_tool") == "My cool tool"
        assert derive_short_description("", "get_weather") == "Get weather"

    def test_handles_exclamation(self):
        desc = "Warning! This is important. More info."
        result = derive_short_description(desc, "x")
        assert result.startswith("Warning!")

    def test_handles_question(self):
        """Test extraction with question mark delimiter."""
        desc = "Is this valid? Yes it is."
        result = derive_short_description(desc, "x")
        assert result == "Is this valid?"

    def test_empty_fallback_name(self):
        """Test with empty fallback name."""
        result = derive_short_description(None, "")
        assert result == "No description available."


# ============================================================================
# Logger Tests
# ============================================================================


class TestMCPStatLogger:
    """Tests for MCPStatLogger."""

    def test_disabled_by_default(self):
        logger = MCPStatLogger(None)
        assert not logger.enabled
        logger.log("test", "tool")  # Should not raise

    def test_enabled_with_path(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_file = Path(tmp_dir) / "test.log"
            logger = MCPStatLogger(str(log_file))
            assert logger.enabled

            logger.log("test_tool", "tool", success=True)
            logger.log("test_prompt", "prompt", success=False, error_msg="Error")
            logger.close()

            content = log_file.read_text()
            assert "tool:test_tool|OK" in content
            assert "prompt:test_prompt|FAIL|Error" in content

    def test_creates_directory(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_file = Path(tmp_dir) / "nested" / "dir" / "test.log"
            logger = MCPStatLogger(str(log_file))
            logger.log("test", "tool")
            logger.close()
            assert log_file.exists()


# ============================================================================
# Database Tests
# ============================================================================


@pytest.fixture
def db_fixture():
    """Create a temporary database for testing."""
    tmp_dir = tempfile.TemporaryDirectory()
    db = MCPStatDatabase(str(Path(tmp_dir.name) / "test.sqlite"))
    yield db
    tmp_dir.cleanup()


class TestMCPStatDatabase:
    """Tests for MCPStatDatabase."""

    @pytest.mark.asyncio
    async def test_record(self, db_fixture):
        db = db_fixture
        await db.record("tool1", "tool")
        await db.record("tool1", "tool")
        await db.record("prompt1", "prompt")

        stats = await db.get_stats()
        assert stats["total_calls"] == 3
        assert stats["tracked_count"] == 2

    @pytest.mark.asyncio
    async def test_record_with_db_in_current_dir(self):
        """Test database in current directory (no parent path)."""
        import os

        old_cwd = Path.cwd()
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                os.chdir(tmp_dir)
                db = MCPStatDatabase("test.sqlite")  # No path, just filename
                await db.record("tool1", "tool")
                stats = await db.get_stats()
                assert stats["total_calls"] == 1
        finally:
            os.chdir(old_cwd)

    @pytest.mark.asyncio
    async def test_get_stats_with_type_filter(self, db_fixture):
        """Test get_stats with type_filter."""
        db = db_fixture
        await db.record("tool1", "tool")
        await db.record("prompt1", "prompt")

        stats = await db.get_stats(type_filter="tool")
        assert stats["tracked_count"] == 1

    @pytest.mark.asyncio
    async def test_get_stats_with_limit(self, db_fixture):
        """Test get_stats with limit."""
        db = db_fixture
        await db.record("tool1", "tool")
        await db.record("tool2", "tool")
        await db.record("tool3", "tool")

        stats = await db.get_stats(limit=2)
        assert len(stats["stats"]) == 2

    @pytest.mark.asyncio
    async def test_get_stats_exclude_zero(self, db_fixture):
        """Test get_stats excluding zero-count items."""
        db = db_fixture
        tools = [
            {"name": "tool1", "tags": ["a"], "short_description": "T1"},
            {"name": "tool2", "tags": ["b"], "short_description": "T2"},
        ]
        await db.sync_metadata(tools)
        await db.record("tool1", "tool")

        stats = await db.get_stats(include_zero=False)
        assert stats["tracked_count"] == 1

    @pytest.mark.asyncio
    async def test_get_by_type(self, db_fixture):
        db = db_fixture
        await db.record("tool1", "tool")
        await db.record("tool2", "tool")
        await db.record("prompt1", "prompt")
        await db.record("resource1", "resource")

        result = await db.get_by_type()
        assert len(result["by_type"]["tool"]) == 2
        assert len(result["by_type"]["prompt"]) == 1
        assert len(result["by_type"]["resource"]) == 1

    @pytest.mark.asyncio
    async def test_metadata_sync(self, db_fixture):
        db = db_fixture
        tools = [
            {"name": "tool1", "description": "Test 1", "tags": ["a"], "short_description": "T1"},
            {"name": "tool2", "description": "Test 2", "tags": ["b"], "short_description": "T2"},
        ]
        await db.sync_metadata(tools)

        catalog = await db.get_catalog()
        assert catalog["total_tracked"] == 2

    @pytest.mark.asyncio
    async def test_orphan_cleanup(self, db_fixture):
        db = db_fixture
        tools = [
            {"name": "tool1", "tags": ["a"], "short_description": "T1"},
            {"name": "tool2", "tags": ["b"], "short_description": "T2"},
        ]
        await db.sync_metadata(tools)
        await db.sync_metadata([tools[0]], cleanup_orphans=True)

        catalog = await db.get_catalog()
        assert catalog["total_tracked"] == 1

    @pytest.mark.asyncio
    async def test_catalog_filtering(self, db_fixture):
        db = db_fixture
        tools = [
            {"name": "get_weather", "tags": ["api", "weather"], "short_description": "Weather"},
            {"name": "get_news", "tags": ["api", "news"], "short_description": "News"},
        ]
        await db.sync_metadata(tools)

        result = await db.get_catalog(tags=["weather"])
        assert result["matched"] == 1
        assert result["results"][0]["name"] == "get_weather"

        result = await db.get_catalog(query="news")
        assert result["matched"] == 1

    @pytest.mark.asyncio
    async def test_catalog_with_limit(self, db_fixture):
        """Test catalog with limit parameter."""
        db = db_fixture
        tools = [
            {"name": "tool1", "tags": ["a"], "short_description": "T1"},
            {"name": "tool2", "tags": ["a"], "short_description": "T2"},
            {"name": "tool3", "tags": ["a"], "short_description": "T3"},
        ]
        await db.sync_metadata(tools)

        result = await db.get_catalog(limit=2)
        assert len(result["results"]) == 2

    @pytest.mark.asyncio
    async def test_catalog_without_usage(self, db_fixture):
        """Test catalog with include_usage=False."""
        db = db_fixture
        tools = [{"name": "tool1", "tags": ["a"], "short_description": "T1"}]
        await db.sync_metadata(tools)

        result = await db.get_catalog(include_usage=False)
        assert result["results"][0]["call_count"] is None

    @pytest.mark.asyncio
    async def test_update_metadata(self, db_fixture):
        """Test direct metadata update."""
        db = db_fixture
        await db.update_metadata(
            "test_tool",
            tags=["tag1", "tag2"],
            short_description="Short",
            full_description="Full description",
        )

        catalog = await db.get_catalog()
        assert catalog["total_tracked"] == 1
        assert catalog["results"][0]["tags"] == ["tag1", "tag2"]


# ============================================================================
# Token Tracking Tests
# ============================================================================


class TestTokenTracking:
    """Tests for token tracking functionality."""

    @pytest.mark.asyncio
    async def test_record_with_response_chars(self, db_fixture):
        """Test recording response size for token estimation."""
        db = db_fixture
        await db.record("tool1", "tool", response_chars=1000)

        stats = await db.get_stats()
        tool_stat = stats["stats"][0]

        assert tool_stat["total_response_chars"] == 1000
        assert tool_stat["estimated_tokens"] > 200
        assert tool_stat["estimated_tokens"] < 350

    @pytest.mark.asyncio
    async def test_record_with_actual_tokens(self, db_fixture):
        """Test recording actual token counts."""
        db = db_fixture
        await db.record("tool1", "tool", input_tokens=100, output_tokens=200)

        stats = await db.get_stats()
        tool_stat = stats["stats"][0]

        assert tool_stat["total_input_tokens"] == 100
        assert tool_stat["total_output_tokens"] == 200

    @pytest.mark.asyncio
    async def test_cumulative_token_tracking(self, db_fixture):
        """Test that tokens accumulate across calls."""
        db = db_fixture
        await db.record("tool1", "tool", input_tokens=100, output_tokens=200)
        await db.record("tool1", "tool", input_tokens=50, output_tokens=100)

        stats = await db.get_stats()
        tool_stat = stats["stats"][0]

        assert tool_stat["call_count"] == 2
        assert tool_stat["total_input_tokens"] == 150
        assert tool_stat["total_output_tokens"] == 300

    @pytest.mark.asyncio
    async def test_report_tokens(self, db_fixture):
        """Test report_tokens method for deferred token reporting."""
        db = db_fixture
        await db.record("tool1", "tool")
        await db.report_tokens("tool1", 100, 200)

        stats = await db.get_stats()
        tool_stat = stats["stats"][0]

        assert tool_stat["call_count"] == 1
        assert tool_stat["total_input_tokens"] == 100
        assert tool_stat["total_output_tokens"] == 200

    @pytest.mark.asyncio
    async def test_token_summary(self, db_fixture):
        """Test token_summary in get_stats response."""
        db = db_fixture
        await db.record("tool1", "tool", input_tokens=100, output_tokens=200)
        await db.record("tool2", "tool", input_tokens=50, output_tokens=100)

        stats = await db.get_stats()

        assert "token_summary" in stats
        summary = stats["token_summary"]
        assert summary["total_input_tokens"] == 150
        assert summary["total_output_tokens"] == 300
        assert summary["has_actual_tokens"]

    @pytest.mark.asyncio
    async def test_avg_tokens_per_call(self, db_fixture):
        """Test average tokens per call calculation."""
        db = db_fixture
        await db.record("tool1", "tool", input_tokens=100, output_tokens=200)
        await db.record("tool1", "tool", input_tokens=200, output_tokens=400)

        stats = await db.get_stats()
        tool_stat = stats["stats"][0]

        assert tool_stat["avg_tokens_per_call"] == 450

    @pytest.mark.asyncio
    async def test_estimated_vs_actual_tokens(self, db_fixture):
        """Test that actual tokens take precedence in avg calculation."""
        db = db_fixture
        await db.record("tool1", "tool", response_chars=1000)

        stats1 = await db.get_stats()
        tool_stat1 = stats1["stats"][0]
        assert tool_stat1["avg_tokens_per_call"] > 0

        await db.report_tokens("tool1", 50, 100)

        stats2 = await db.get_stats()
        tool_stat2 = stats2["stats"][0]
        assert tool_stat2["avg_tokens_per_call"] == 150


class TestSchemaMigration:
    """Tests for schema migration from v1 to v2."""

    @pytest.mark.asyncio
    async def test_migration_adds_columns(self):
        """Test that v1 databases are migrated to v2."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "test.sqlite")

            conn = sqlite3.connect(db_path)
            conn.executescript("""
                CREATE TABLE mcpstat_meta (key TEXT PRIMARY KEY, value TEXT);
                INSERT INTO mcpstat_meta (key, value) VALUES ('schema_version', '1');

                CREATE TABLE mcpstat_usage (
                    name TEXT PRIMARY KEY,
                    type TEXT NOT NULL DEFAULT 'tool',
                    call_count INTEGER NOT NULL DEFAULT 0,
                    last_accessed TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE mcpstat_metadata (
                    name TEXT PRIMARY KEY,
                    tags TEXT DEFAULT '',
                    short_description TEXT,
                    full_description TEXT
                );

                INSERT INTO mcpstat_usage (name, type, call_count, last_accessed, created_at)
                VALUES ('old_tool', 'tool', 5, '2024-01-01', '2024-01-01');
            """)
            conn.close()

            db = MCPStatDatabase(db_path)

            stats = await db.get_stats()
            tool_stat = next(s for s in stats["stats"] if s["name"] == "old_tool")

            assert tool_stat["call_count"] == 5
            assert tool_stat["total_input_tokens"] == 0
            assert tool_stat["total_output_tokens"] == 0
            assert tool_stat["estimated_tokens"] == 0

            await db.record("old_tool", "tool", input_tokens=100)
            stats2 = await db.get_stats()
            tool_stat2 = next(s for s in stats2["stats"] if s["name"] == "old_tool")
            assert tool_stat2["total_input_tokens"] == 100


# ============================================================================
# Core Tests
# ============================================================================


@pytest.fixture
def stat_fixture():
    """Create a temporary MCPStat instance for testing."""
    tmp_dir = tempfile.TemporaryDirectory()
    stat = MCPStat(
        "test-server",
        db_path=str(Path(tmp_dir.name) / "test.sqlite"),
        log_enabled=False,
    )
    yield stat
    stat.close()
    tmp_dir.cleanup()


class TestMCPStat:
    """Tests for main MCPStat class."""

    @pytest.mark.asyncio
    async def test_record_and_stats(self, stat_fixture):
        stat = stat_fixture
        await stat.record("tool1", "tool")
        await stat.record("tool1", "tool")
        await stat.record("prompt1", "prompt")

        stats = await stat.get_stats()
        assert stats["total_calls"] == 3

    @pytest.mark.asyncio
    async def test_record_with_token_tracking(self, stat_fixture):
        """Test record with token tracking in MCPStat."""
        stat = stat_fixture
        await stat.record("tool1", "tool", response_chars=500, input_tokens=50, output_tokens=100)
        stats = await stat.get_stats()
        assert stats["stats"][0]["total_input_tokens"] == 50
        assert stats["stats"][0]["total_output_tokens"] == 100

    @pytest.mark.asyncio
    async def test_report_tokens(self, stat_fixture):
        """Test report_tokens method in MCPStat."""
        stat = stat_fixture
        await stat.record("tool1", "tool")
        await stat.report_tokens("tool1", 100, 200)
        stats = await stat.get_stats()
        assert stats["stats"][0]["total_input_tokens"] == 100

    @pytest.mark.asyncio
    async def test_sync_prompts(self, stat_fixture):
        """Test sync_prompts method."""
        stat = stat_fixture

        class MockPrompt:
            name = "test_prompt"
            description = "A test prompt"

        await stat.sync_prompts([MockPrompt()])
        catalog = await stat.get_catalog()
        assert len(catalog["results"]) == 1
        assert catalog["results"][0]["name"] == "test_prompt"

    @pytest.mark.asyncio
    async def test_sync_prompts_with_preset(self, stat_fixture):
        """Test sync_prompts with preset metadata."""
        stat = stat_fixture
        stat.add_preset("preset_prompt", tags=["custom"], short="Custom prompt")

        class MockPrompt:
            name = "preset_prompt"
            description = "Full description"

        await stat.sync_prompts([MockPrompt()])
        catalog = await stat.get_catalog()
        assert "custom" in catalog["results"][0]["tags"]

    @pytest.mark.asyncio
    async def test_sync_resources(self, stat_fixture):
        """Test sync_resources method."""
        stat = stat_fixture

        class MockResource:
            name = "test_resource"
            description = "A test resource"

        await stat.sync_resources([MockResource()])
        catalog = await stat.get_catalog()
        assert len(catalog["results"]) == 1
        assert catalog["results"][0]["name"] == "test_resource"

    @pytest.mark.asyncio
    async def test_sync_resources_with_uri(self, stat_fixture):
        """Test sync_resources with URI instead of name."""
        stat = stat_fixture

        class MockResource:
            uri = "resource://test/data"
            description = "A test resource"

        await stat.sync_resources([MockResource()])
        catalog = await stat.get_catalog()
        assert len(catalog["results"]) == 1
        assert "resource://test/data" in catalog["results"][0]["name"]

    @pytest.mark.asyncio
    async def test_sync_resources_with_preset(self, stat_fixture):
        """Test sync_resources with preset metadata."""
        stat = stat_fixture
        stat.add_preset("preset_resource", tags=["data"], short="Preset resource")

        class MockResource:
            name = "preset_resource"
            description = "Full description"

        await stat.sync_resources([MockResource()])
        catalog = await stat.get_catalog()
        assert "data" in catalog["results"][0]["tags"]

    @pytest.mark.asyncio
    async def test_record_with_failure(self, stat_fixture):
        """Test recording failed invocations."""
        stat = stat_fixture
        await stat.record("tool1", "tool", success=False, error_msg="Test error")
        stats = await stat.get_stats()
        assert stats["total_calls"] == 1

    @pytest.mark.asyncio
    async def test_get_by_type(self, stat_fixture):
        """Test get_by_type method."""
        stat = stat_fixture
        await stat.record("tool1", "tool")
        await stat.record("prompt1", "prompt")

        result = await stat.get_by_type()
        assert "by_type" in result
        assert "summary" in result

    @pytest.mark.asyncio
    async def test_get_catalog(self, stat_fixture):
        """Test get_catalog method."""
        stat = stat_fixture
        await stat.register_metadata(
            "test_tool", tags=["api", "test"], short_description="Test tool"
        )

        catalog = await stat.get_catalog(tags=["api"])
        assert "results" in catalog
        assert "all_tags" in catalog

    @pytest.mark.asyncio
    async def test_metadata_presets(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            stat = MCPStat(
                "test",
                db_path=str(Path(tmp_dir) / "test.sqlite"),
                metadata_presets={"my_tool": {"tags": ["custom"], "short": "Custom desc"}},
            )

            class MockTool:
                name = "my_tool"
                description = "Full description"

            await stat.sync_tools([MockTool()])
            catalog = await stat.get_catalog()

            tool = catalog["results"][0]
            assert "custom" in tool["tags"]
            assert tool["short_description"] == "Custom desc"
            stat.close()

    @pytest.mark.asyncio
    async def test_sync_tools_without_preset(self, stat_fixture):
        """Test sync_tools auto-generates tags when no preset."""
        stat = stat_fixture

        class MockTool:
            name = "fetch_data"
            description = "Fetch data from API"

        await stat.sync_tools([MockTool()])
        catalog = await stat.get_catalog()

        assert len(catalog["results"]) == 1
        tool = catalog["results"][0]
        assert "fetch_data" in tool["tags"]

    @pytest.mark.asyncio
    async def test_sync_tools_with_stopword_name(self, stat_fixture):
        """Test sync_tools with tool name that would produce empty tags (all stopwords)."""
        stat = stat_fixture

        class MockTool:
            name = "to"  # All words are stopwords
            description = None

        await stat.sync_tools([MockTool()])
        catalog = await stat.get_catalog()

        assert len(catalog["results"]) == 1
        tool = catalog["results"][0]
        # Should fallback to name.lower() as tag
        assert "to" in tool["tags"]

    def test_add_preset(self, stat_fixture):
        """Test add_preset method."""
        stat = stat_fixture
        stat.add_preset("new_tool", tags=["custom"], short="Description")
        assert "new_tool" in stat.metadata_presets

    @pytest.mark.asyncio
    async def test_register_metadata(self, stat_fixture):
        """Test manual metadata registration."""
        stat = stat_fixture
        await stat.register_metadata(
            "manual_tool",
            tags=["manual", "test"],
            short_description="Manually registered",
            full_description="Full description here",
        )

        catalog = await stat.get_catalog()
        assert len(catalog["results"]) == 1
        assert catalog["results"][0]["name"] == "manual_tool"

    def test_env_var_log_enabled_true(self):
        """Test MCPSTAT_LOG_ENABLED=true."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            old_val = os.environ.get("MCPSTAT_LOG_ENABLED")
            try:
                os.environ["MCPSTAT_LOG_ENABLED"] = "true"
                stat = MCPStat("test", db_path=str(Path(tmp_dir) / "test.sqlite"))
                assert stat.log_enabled
                stat.close()
            finally:
                if old_val is None:
                    os.environ.pop("MCPSTAT_LOG_ENABLED", None)
                else:
                    os.environ["MCPSTAT_LOG_ENABLED"] = old_val

    def test_env_var_log_enabled_false(self):
        """Test MCPSTAT_LOG_ENABLED=false."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            old_val = os.environ.get("MCPSTAT_LOG_ENABLED")
            try:
                os.environ["MCPSTAT_LOG_ENABLED"] = "false"
                stat = MCPStat("test", db_path=str(Path(tmp_dir) / "test.sqlite"))
                assert not stat.log_enabled
                stat.close()
            finally:
                if old_val is None:
                    os.environ.pop("MCPSTAT_LOG_ENABLED", None)
                else:
                    os.environ["MCPSTAT_LOG_ENABLED"] = old_val


# ============================================================================
# Prompt Tests
# ============================================================================


class TestPrompts:
    """Tests for prompt functions."""

    def test_build_prompt_definition(self):
        defn = build_prompt_definition("test_stats", "Test Server")
        assert defn["name"] == "test_stats"
        assert len(defn["arguments"]) == 3

    @pytest.mark.asyncio
    async def test_generate_stats_prompt(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            stat = MCPStat("test", db_path=str(Path(tmp_dir) / "test.sqlite"))
            await stat.record("tool1", "tool")
            await stat.record("prompt1", "prompt")

            text = await generate_stats_prompt(stat)
            assert "MCP Usage Statistics" in text
            assert "Tools" in text
            assert "Prompts" in text
            stat.close()

    @pytest.mark.asyncio
    async def test_generate_stats_prompt_with_type_filter(self):
        """Test generate_stats_prompt with type filter."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            stat = MCPStat("test", db_path=str(Path(tmp_dir) / "test.sqlite"))
            await stat.record("tool1", "tool")
            await stat.record("resource1", "resource")

            # Filter to tools only
            text = await generate_stats_prompt(stat, type_filter="tool")
            assert "Tools" in text
            assert "Resources" not in text

            # Filter to resources only
            text = await generate_stats_prompt(stat, type_filter="resource")
            assert "Resources" in text
            assert "Tools" not in text

            # Filter to prompts only
            text = await generate_stats_prompt(stat, type_filter="prompt")
            assert "Prompts" in text
            assert "Tools" not in text
            stat.close()

    @pytest.mark.asyncio
    async def test_generate_stats_prompt_without_recommendations(self):
        """Test generate_stats_prompt without recommendations."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            stat = MCPStat("test", db_path=str(Path(tmp_dir) / "test.sqlite"))
            await stat.record("tool1", "tool")

            text = await generate_stats_prompt(stat, include_recommendations=False)
            assert "Recommendations" not in text
            stat.close()

    @pytest.mark.asyncio
    async def test_generate_stats_prompt_all_used(self):
        """Test format_unused returns 'All have been used' when all tools have calls."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            stat = MCPStat("test", db_path=str(Path(tmp_dir) / "test.sqlite"))
            # Only record calls, no zero-use items
            await stat.record("tool1", "tool")
            await stat.record("tool2", "tool")

            text = await generate_stats_prompt(stat)
            assert "All have been used" in text
            stat.close()

    @pytest.mark.asyncio
    async def test_handle_stats_prompt(self):
        """Test handle_stats_prompt function."""
        from mcpstat.prompts import handle_stats_prompt

        with tempfile.TemporaryDirectory() as tmp_dir:
            stat = MCPStat("test", db_path=str(Path(tmp_dir) / "test.sqlite"))
            await stat.record("tool1", "tool")

            result = await handle_stats_prompt(stat)
            assert "description" in result
            assert "messages" in result
            assert len(result["messages"]) == 1
            assert "MCP Usage Statistics" in result["messages"][0]["content"]["text"]
            stat.close()

    @pytest.mark.asyncio
    async def test_handle_stats_prompt_with_args(self):
        """Test handle_stats_prompt with arguments."""
        from mcpstat.prompts import handle_stats_prompt

        with tempfile.TemporaryDirectory() as tmp_dir:
            stat = MCPStat("test", db_path=str(Path(tmp_dir) / "test.sqlite"))
            await stat.record("tool1", "tool")

            result = await handle_stats_prompt(
                stat,
                arguments={
                    "period": "last week",
                    "type": "tool",
                    "include_recommendations": "no",
                },
            )
            assert "last week" in result["description"]
            assert "Recommendations" not in result["messages"][0]["content"]["text"]
            stat.close()


# ============================================================================
# Tools Tests
# ============================================================================


class TestTools:
    """Tests for tool functions."""

    def test_build_tool_definitions(self):
        tools = build_tool_definitions(prefix="get", server_name="test")
        assert len(tools) == 2
        assert any(t["name"] == "get_tool_usage_stats" for t in tools)
        assert any(t["name"] == "get_tool_catalog" for t in tools)

    def test_build_tool_definitions_custom_prefix(self):
        """Test with custom prefix."""
        tools = build_tool_definitions(prefix="fetch", server_name="my-server")
        assert any(t["name"] == "fetch_tool_usage_stats" for t in tools)
        assert any(t["name"] == "fetch_tool_catalog" for t in tools)


class TestBuiltinToolsHandler:
    """Tests for BuiltinToolsHandler class."""

    def test_is_stats_tool(self, stat_fixture):
        """Test is_stats_tool detection."""
        handler = BuiltinToolsHandler(stat_fixture, prefix="get")
        assert handler.is_stats_tool("get_tool_usage_stats")
        assert handler.is_stats_tool("get_tool_catalog")
        assert not handler.is_stats_tool("other_tool")

    @pytest.mark.asyncio
    async def test_handle_usage_stats(self, stat_fixture):
        """Test handling get_tool_usage_stats."""
        handler = BuiltinToolsHandler(stat_fixture, prefix="get")

        await stat_fixture.record("tool1", "tool")
        result = await handler.handle("get_tool_usage_stats", {})

        assert result is not None
        assert "tracked_count" in result
        assert "total_calls" in result

    @pytest.mark.asyncio
    async def test_handle_catalog(self, stat_fixture):
        """Test handling get_tool_catalog."""
        handler = BuiltinToolsHandler(stat_fixture, prefix="get")

        await stat_fixture.register_metadata("test_tool", tags=["api"], short_description="Test")
        result = await handler.handle("get_tool_catalog", {"tags": ["api"]})

        assert result is not None
        assert "total_tracked" in result
        assert "results" in result

    @pytest.mark.asyncio
    async def test_handle_unknown_tool(self, stat_fixture):
        """Test handling unknown tool returns None."""
        handler = BuiltinToolsHandler(stat_fixture, prefix="get")

        result = await handler.handle("unknown_tool", {})
        assert result is None

    def test_custom_prefix(self, stat_fixture):
        """Test handler with custom prefix."""
        handler = BuiltinToolsHandler(stat_fixture, prefix="stats")
        assert handler.is_stats_tool("stats_tool_usage_stats")
        assert not handler.is_stats_tool("get_tool_usage_stats")
