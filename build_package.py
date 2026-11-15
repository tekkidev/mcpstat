"""
mcpstat - Usage tracking and analytics for MCP servers.
https://github.com/tekkidev/mcpstat

Copyright (c) 2026 Vadim Bakhrenkov
SPDX-License-Identifier: MIT

Include public documentation resources in source and wheel distributions.
"""

from pathlib import Path
from shutil import copyfile


def build() -> None:
    root = Path(__file__).parent
    target = root / "mcpstat" / "_docs"
    target.mkdir(exist_ok=True)
    for name in (
        "README.md",
        "llms.txt",
        "llms-full.txt",
        "docs/quickstart.md",
        "docs/api.md",
        "docs/configuration.md",
        "docs/token-tracking.md",
        "docs/latency-tracking.md",
    ):
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        copyfile(root / name, destination)


if __name__ == "__main__":
    build()
