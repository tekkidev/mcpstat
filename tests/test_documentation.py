"""
mcpstat - Usage tracking and analytics for MCP servers.
https://github.com/tekkidev/mcpstat

Copyright (c) 2026 Vadim Bakhrenkov
SPDX-License-Identifier: MIT

This module validates the structure and content of mcpstat documentation.
"""

from pathlib import Path

import pytest


class TestDocumentation:
    """Tests for documentation files."""

    @pytest.fixture
    def readme_path(self) -> Path:
        """Return path to main README.md."""
        return Path(__file__).parent.parent / "README.md"

    @pytest.fixture
    def docs_path(self) -> Path:
        """Return path to docs directory."""
        return Path(__file__).parent.parent / "docs"

    @pytest.fixture
    def changelog_path(self) -> Path:
        """Return path to CHANGELOG.md."""
        return Path(__file__).parent.parent / "CHANGELOG.md"

    def test_readme_has_quick_start(self, readme_path: Path) -> None:
        """Test that main README has quick start section."""
        content = readme_path.read_text()
        assert "Quick Start" in content, "Main README should have Quick Start section"

    def test_readme_has_installation(self, readme_path: Path) -> None:
        """Test that main README has installation instructions."""
        content = readme_path.read_text()
        assert "pip install mcpstat" in content, "Main README should have installation instructions"

    def test_readme_has_features(self, readme_path: Path) -> None:
        """Test that main README has features section."""
        content = readme_path.read_text()
        assert "Features" in content, "Main README should have Features section"

    def test_readme_has_license(self, readme_path: Path) -> None:
        """Test that main README mentions license."""
        content = readme_path.read_text()
        assert "MIT" in content, "Main README should mention MIT license"

    def test_required_docs_exist(self, docs_path: Path) -> None:
        """Test that required documentation files exist."""
        required_docs = [
            "index.md",
            "quickstart.md",
            "configuration.md",
            "api.md",
            "token-tracking.md",
        ]
        for doc in required_docs:
            doc_path = docs_path / doc
            assert doc_path.exists(), f"docs/{doc} should exist"

    def test_token_tracking_doc_exists_and_valid(self, docs_path: Path) -> None:
        """Test that token-tracking.md exists and has key content."""
        token_path = docs_path / "token-tracking.md"
        content = token_path.read_text()

        # Check for key concepts
        assert "response_chars" in content, "token-tracking should mention response_chars"
        assert "input_tokens" in content, "token-tracking should mention input_tokens"
        assert "output_tokens" in content, "token-tracking should mention output_tokens"
        assert "report_tokens" in content, "token-tracking should mention report_tokens"

    def test_changelog_exists_and_valid(self, changelog_path: Path) -> None:
        """Test that CHANGELOG.md exists and follows Keep a Changelog format."""
        content = changelog_path.read_text()

        assert "# Changelog" in content, "CHANGELOG should have title"
        assert "[Unreleased]" in content, "CHANGELOG should have Unreleased section"
        assert "Keep a Changelog" in content, "CHANGELOG should reference Keep a Changelog"

    def test_quickstart_mentions_mcpstat(self, docs_path: Path) -> None:
        """Test that quickstart mentions MCPStat class."""
        quickstart_path = docs_path / "quickstart.md"
        content = quickstart_path.read_text()

        assert "MCPStat" in content, "quickstart should mention MCPStat class"
        assert "stat.record" in content, "quickstart should mention stat.record()"

    def test_api_doc_has_methods(self, docs_path: Path) -> None:
        """Test that API docs mention key methods."""
        api_path = docs_path / "api.md"
        content = api_path.read_text()

        assert "record" in content, "API docs should mention record method"
        assert "get_stats" in content, "API docs should mention get_stats method"
        assert "get_catalog" in content, "API docs should mention get_catalog method"
