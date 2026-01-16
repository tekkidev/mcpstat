"""
MCPStat - Usage tracking and analytics for MCP servers.
https://github.com/tekkidev/mcpstat

Copyright (c) 2026 Vadim Bakhrenkov
SPDX-License-Identifier: MIT

Utility functions for mcpstat.

Pure functions with no side effects - safe for concurrent use.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

# Common stopwords to filter from auto-generated tags
_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "get", "has", "have", "in", "is", "it", "its", "of", "on", "or",
    "that", "the", "this", "to", "was", "will", "with",
})


def normalize_tags(tags: Iterable[str], *, filter_stopwords: bool = False) -> list[str]:
    """Normalize and deduplicate tags into a stable, lowercase list.

    Handles:
    - Whitespace normalization
    - Case normalization (lowercase)
    - Empty string removal
    - Duplicate removal (preserving first occurrence order)
    - Optional stopword filtering for auto-generated tags

    Args:
        tags: Raw tag strings (may contain duplicates, mixed case, whitespace)
        filter_stopwords: Remove common stopwords like "to", "from", "the"

    Returns:
        Deduplicated, normalized tag list in original order

    Example:
        >>> normalize_tags(["Test", "test", "  HELLO  ", "world", ""])
        ['test', 'hello', 'world']
        >>> normalize_tags(["convert", "to", "celsius"], filter_stopwords=True)
        ['convert', 'celsius']
    """
    result: list[str] = []
    seen: set[str] = set()

    for tag in tags:
        if not tag:
            continue
        # Collapse whitespace and normalize case
        normalized = re.sub(r"\s+", " ", str(tag).strip().lower())
        if not normalized or normalized in seen:
            continue
        # Filter stopwords if requested (but always keep tags > 3 chars with underscores)
        if filter_stopwords and normalized in _STOPWORDS and "_" not in normalized:
            continue
        result.append(normalized)
        seen.add(normalized)

    return result


def derive_short_description(
    description: str | None,
    fallback_name: str,
    max_length: int = 160,
) -> str:
    """Generate a compact summary suitable for quick scanning.

    Extracts the first sentence from a description, or generates
    a human-readable fallback from the tool name.

    Args:
        description: Full description text (may be None or empty)
        fallback_name: Name to humanize if no description
        max_length: Maximum output length (default: 160)

    Returns:
        Short description, never exceeds max_length

    Example:
        >>> derive_short_description("Get weather data. Supports multiple formats.", "get_weather")
        'Get weather data.'
        >>> derive_short_description(None, "my_cool_tool")
        'My cool tool'
    """
    base = (description or "").strip()

    if base:
        # Collapse whitespace
        collapsed = " ".join(base.split())

        # Extract first sentence
        for delimiter in (". ", "! ", "? "):
            idx = collapsed.find(delimiter)
            if idx != -1:
                collapsed = collapsed[: idx + 1]
                break

        # Truncate if needed
        if len(collapsed) > max_length:
            return collapsed[: max_length - 3].rstrip() + "..."
        return collapsed

    # Generate from name: my_cool_tool -> "My cool tool"
    readable = fallback_name.replace("_", " ").replace("-", " ").strip().capitalize()
    return readable or "No description available."


def parse_tags_string(value: str | None) -> list[str]:
    """Parse comma-separated tags string into list.

    Args:
        value: Comma-separated string or None

    Returns:
        List of non-empty, stripped tags
    """
    if not value:
        return []
    return [t.strip() for t in value.split(",") if t.strip()]


def tags_to_string(tags: list[str]) -> str:
    """Convert tags list to comma-separated string for storage.

    Args:
        tags: List of tags

    Returns:
        Comma-separated string
    """
    return ",".join(tags)
