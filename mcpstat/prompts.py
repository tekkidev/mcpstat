"""
MCPStat - Usage tracking and analytics for MCP servers.
https://github.com/tekkidev/mcpstat

Copyright (c) 2026 Vadim Bakhrenkov
SPDX-License-Identifier: MIT

Built-in prompts for mcpstat.

Provides the stats prompt generator for LLM-friendly usage reports.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcpstat.core import MCPStat


async def generate_stats_prompt(
    stat: MCPStat,
    *,
    period: str = "all time",
    type_filter: str = "all",
    include_recommendations: bool = True,
) -> str:
    """Generate MCP usage statistics prompt text.

    Creates a formatted markdown report suitable for LLM consumption,
    grouped by MCP primitive type.

    Args:
        stat: McpStat instance
        period: Time period description for context
        type_filter: Filter by type (all/tool/resource/prompt)
        include_recommendations: Include adoption recommendations

    Returns:
        Formatted markdown prompt text
    """
    type_filter = type_filter.lower()

    # Fetch usage data grouped by type
    data = await stat.get_by_type()
    by_type = data["by_type"]
    summary = data["summary"]
    total = data["total_calls"]

    def format_top(items: list[dict[str, Any]], limit: int = 5) -> str:
        """Format top N items as numbered list."""
        used = [i for i in items if i.get("call_count", 0) > 0][:limit]
        if not used:
            return "(None used yet)"
        return "\n".join(
            f"{i+1}. `{item['name']}` - **{item['call_count']} calls**"
            for i, item in enumerate(used)
        )

    def format_unused(items: list[dict[str, Any]]) -> str:
        """Format unused items as bullet list."""
        unused = [i for i in items if i.get("call_count", 0) == 0]
        if not unused:
            return "(All have been used)"
        return "\n".join(f"- `{i['name']}`" for i in unused)

    # Build summary line
    parts = []
    for t in ["tool", "resource", "prompt"]:
        if t in summary:
            cnt = summary[t]["count"]
            calls = summary[t]["total_calls"]
            parts.append(f"{cnt} {t}s ({calls} calls)")
    summary_line = ", ".join(parts) if parts else "No data"

    # Build sections
    sections = []

    if type_filter in ("all", "tool"):
        ts = summary.get("tool", {})
        sections.append(f"""### 🔧 Tools ({ts.get('count', 0)} tracked, {ts.get('total_calls', 0)} calls)

**Top 5:**
{format_top(by_type.get('tool', []))}

**Unused:**
{format_unused(by_type.get('tool', []))}""")

    if type_filter in ("all", "resource"):
        rs = summary.get("resource", {})
        sections.append(f"""### 📚 Resources ({rs.get('count', 0)} tracked, {rs.get('total_calls', 0)} calls)

**Top 5:**
{format_top(by_type.get('resource', []))}

**Unused:**
{format_unused(by_type.get('resource', []))}""")

    if type_filter in ("all", "prompt"):
        ps = summary.get("prompt", {})
        sections.append(f"""### 💬 Prompts ({ps.get('count', 0)} tracked, {ps.get('total_calls', 0)} calls)

**Top 5:**
{format_top(by_type.get('prompt', []))}

**Unused:**
{format_unused(by_type.get('prompt', []))}""")

    recs = ""
    if include_recommendations:
        recs = """

---
**Recommendations:**
1. High-usage tools represent key workflows - ensure robust error handling
2. Unused items may need better documentation or deprecation
3. Consider promoting underused tools that provide value"""

    filter_note = f" (filtered: {type_filter})" if type_filter != "all" else ""

    return f"""## MCP Usage Statistics{filter_note}

**Summary:** {summary_line}
**Total:** {total} calls across all primitives

{chr(10).join(sections)}
{recs}

---
_Period: {period}_"""


def build_prompt_definition(
    prompt_name: str,
    server_name: str = "MCP server",
) -> dict[str, Any]:
    """Build prompt definition dictionary for MCP registration.

    Args:
        prompt_name: Name for the stats prompt
        server_name: Server name for description

    Returns:
        Dictionary suitable for MCP Prompt creation
    """
    return {
        "name": prompt_name,
        "description": f"Generate {server_name} usage statistics summary with sections for tools, resources, and prompts",
        "arguments": [
            {
                "name": "period",
                "description": "Time period description (e.g., 'past week', 'since deployment')",
                "required": False,
            },
            {
                "name": "type",
                "description": "Filter by type: 'all' (default), 'tool', 'resource', or 'prompt'",
                "required": False,
            },
            {
                "name": "include_recommendations",
                "description": "Include adoption recommendations (yes/no, default: yes)",
                "required": False,
            },
        ],
    }


async def handle_stats_prompt(
    stat: MCPStat,
    arguments: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Handle stats prompt request.

    Args:
        stat: MCPStat instance
        arguments: Prompt arguments from MCP request

    Returns:
        GetPromptResult-compatible dictionary
    """
    args = arguments or {}

    text = await generate_stats_prompt(
        stat,
        period=args.get("period", "all time"),
        type_filter=args.get("type", "all"),
        include_recommendations=args.get("include_recommendations", "yes").lower() != "no",
    )

    return {
        "description": f"MCP usage statistics for {args.get('period', 'all time')}",
        "messages": [{"role": "user", "content": {"type": "text", "text": text}}],
    }
