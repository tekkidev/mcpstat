"""
MCPStat - Usage tracking and analytics for MCP servers.
https://github.com/tekkidev/mcpstat

Copyright (c) 2026 Vadim Bakhrenkov
SPDX-License-Identifier: MIT

Tests for mcpstat package.

Uses only stdlib unittest - no pytest required.
"""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from mcpstat import (
    MCPStat,
    MCPStatDatabase,
    MCPStatLogger,
    build_prompt_definition,
    build_tool_definitions,
    derive_short_description,
    generate_stats_prompt,
    normalize_tags,
)


def run_async(coro):
    """Run async coroutine synchronously."""
    return asyncio.new_event_loop().run_until_complete(coro)


# ============================================================================
# Utils Tests
# ============================================================================


class TestNormalizeTags(unittest.TestCase):
    """Tests for normalize_tags function."""

    def test_basic(self):
        tags = ["Test", "test", "  HELLO  ", "world", ""]
        self.assertEqual(normalize_tags(tags), ["test", "hello", "world"])

    def test_empty(self):
        self.assertEqual(normalize_tags([]), [])
        self.assertEqual(normalize_tags([""]), [])
        self.assertEqual(normalize_tags(["", "  "]), [])

    def test_preserves_order(self):
        self.assertEqual(normalize_tags(["b", "a", "c"]), ["b", "a", "c"])

    def test_deduplicates(self):
        self.assertEqual(normalize_tags(["a", "A", "a"]), ["a"])


class TestDeriveShortDescription(unittest.TestCase):
    """Tests for derive_short_description function."""

    def test_extracts_first_sentence(self):
        desc = "Get weather data. Supports multiple formats."
        self.assertEqual(derive_short_description(desc, "x"), "Get weather data.")

    def test_truncates_long(self):
        desc = "A" * 200
        result = derive_short_description(desc, "x")
        self.assertLessEqual(len(result), 160)
        self.assertTrue(result.endswith("..."))

    def test_fallback_to_name(self):
        self.assertEqual(derive_short_description(None, "my_cool_tool"), "My cool tool")
        self.assertEqual(derive_short_description("", "get_weather"), "Get weather")

    def test_handles_exclamation(self):
        desc = "Warning! This is important. More info."
        result = derive_short_description(desc, "x")
        self.assertTrue(result.startswith("Warning!"))


# ============================================================================
# Logger Tests
# ============================================================================


class TestMCPStatLogger(unittest.TestCase):
    """Tests for MCPStatLogger."""

    def test_disabled_by_default(self):
        logger = MCPStatLogger(None)
        self.assertFalse(logger.enabled)
        logger.log("test", "tool")  # Should not raise

    def test_enabled_with_path(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_file = Path(tmp_dir) / "test.log"
            logger = MCPStatLogger(str(log_file))
            self.assertTrue(logger.enabled)

            logger.log("test_tool", "tool", success=True)
            logger.log("test_prompt", "prompt", success=False, error_msg="Error")
            logger.close()

            content = log_file.read_text()
            self.assertIn("tool:test_tool|OK", content)
            self.assertIn("prompt:test_prompt|FAIL|Error", content)

    def test_creates_directory(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_file = Path(tmp_dir) / "nested" / "dir" / "test.log"
            logger = MCPStatLogger(str(log_file))
            logger.log("test", "tool")
            logger.close()
            self.assertTrue(log_file.exists())


# ============================================================================
# Database Tests
# ============================================================================


class TestMCPStatDatabase(unittest.TestCase):
    """Tests for MCPStatDatabase."""

    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.db = MCPStatDatabase(str(Path(self._tmp_dir.name) / "test.sqlite"))

    def tearDown(self):
        self._tmp_dir.cleanup()

    def test_record(self):
        run_async(self.db.record("tool1", "tool"))
        run_async(self.db.record("tool1", "tool"))
        run_async(self.db.record("prompt1", "prompt"))

        stats = run_async(self.db.get_stats())
        self.assertEqual(stats["total_calls"], 3)
        self.assertEqual(stats["tracked_count"], 2)

    def test_get_by_type(self):
        run_async(self.db.record("tool1", "tool"))
        run_async(self.db.record("tool2", "tool"))
        run_async(self.db.record("prompt1", "prompt"))
        run_async(self.db.record("resource1", "resource"))

        result = run_async(self.db.get_by_type())
        self.assertEqual(len(result["by_type"]["tool"]), 2)
        self.assertEqual(len(result["by_type"]["prompt"]), 1)
        self.assertEqual(len(result["by_type"]["resource"]), 1)

    def test_metadata_sync(self):
        tools = [
            {"name": "tool1", "description": "Test 1", "tags": ["a"], "short_description": "T1"},
            {"name": "tool2", "description": "Test 2", "tags": ["b"], "short_description": "T2"},
        ]
        run_async(self.db.sync_metadata(tools))

        catalog = run_async(self.db.get_catalog())
        self.assertEqual(catalog["total_tracked"], 2)

    def test_orphan_cleanup(self):
        tools = [
            {"name": "tool1", "tags": ["a"], "short_description": "T1"},
            {"name": "tool2", "tags": ["b"], "short_description": "T2"},
        ]
        run_async(self.db.sync_metadata(tools))

        # Remove one
        run_async(self.db.sync_metadata([tools[0]], cleanup_orphans=True))

        catalog = run_async(self.db.get_catalog())
        self.assertEqual(catalog["total_tracked"], 1)

    def test_catalog_filtering(self):
        tools = [
            {"name": "get_weather", "tags": ["api", "weather"], "short_description": "Weather"},
            {"name": "get_news", "tags": ["api", "news"], "short_description": "News"},
        ]
        run_async(self.db.sync_metadata(tools))

        # Filter by tag
        result = run_async(self.db.get_catalog(tags=["weather"]))
        self.assertEqual(result["matched"], 1)
        self.assertEqual(result["results"][0]["name"], "get_weather")

        # Text search
        result = run_async(self.db.get_catalog(query="news"))
        self.assertEqual(result["matched"], 1)


# ============================================================================
# Core Tests
# ============================================================================


class TestMCPStat(unittest.TestCase):
    """Tests for main MCPStat class."""

    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.stat = MCPStat(
            "test-server",
            db_path=str(Path(self._tmp_dir.name) / "test.sqlite"),
            log_enabled=False,
        )

    def tearDown(self):
        self.stat.close()
        self._tmp_dir.cleanup()

    def test_record_and_stats(self):
        run_async(self.stat.record("tool1", "tool"))
        run_async(self.stat.record("tool1", "tool"))
        run_async(self.stat.record("prompt1", "prompt"))

        stats = run_async(self.stat.get_stats())
        self.assertEqual(stats["total_calls"], 3)

    def test_metadata_presets(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            stat = MCPStat(
                "test",
                db_path=str(Path(tmp_dir) / "test.sqlite"),
                metadata_presets={
                    "my_tool": {"tags": ["custom"], "short": "Custom desc"}
                }
            )

            # Mock Tool object
            class MockTool:
                name = "my_tool"
                description = "Full description"

            run_async(stat.sync_tools([MockTool()]))
            catalog = run_async(stat.get_catalog())

            tool = catalog["results"][0]
            self.assertIn("custom", tool["tags"])
            self.assertEqual(tool["short_description"], "Custom desc")
            stat.close()


# ============================================================================
# Prompt Tests
# ============================================================================


class TestPrompts(unittest.TestCase):
    """Tests for prompt functions."""

    def test_build_prompt_definition(self):
        defn = build_prompt_definition("test_stats", "Test Server")
        self.assertEqual(defn["name"], "test_stats")
        self.assertEqual(len(defn["arguments"]), 3)

    def test_generate_stats_prompt(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            stat = MCPStat("test", db_path=str(Path(tmp_dir) / "test.sqlite"))
            run_async(stat.record("tool1", "tool"))
            run_async(stat.record("prompt1", "prompt"))

            text = run_async(generate_stats_prompt(stat))
            self.assertIn("MCP Usage Statistics", text)
            self.assertIn("Tools", text)
            self.assertIn("Prompts", text)
            stat.close()


# ============================================================================
# Tools Tests
# ============================================================================


class TestTools(unittest.TestCase):
    """Tests for tool functions."""

    def test_build_tool_definitions(self):
        tools = build_tool_definitions(prefix="get", server_name="test")
        self.assertEqual(len(tools), 2)
        self.assertTrue(any(t["name"] == "get_tool_usage_stats" for t in tools))
        self.assertTrue(any(t["name"] == "get_tool_catalog" for t in tools))


if __name__ == "__main__":
    unittest.main()
