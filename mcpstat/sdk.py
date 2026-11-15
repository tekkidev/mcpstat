"""
mcpstat - Usage tracking and analytics for MCP servers.
https://github.com/tekkidev/mcpstat

Copyright (c) 2026 Vadim Bakhrenkov
SPDX-License-Identifier: MIT

Optional integration controls for the MCP Python SDK.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcp.server import MCPServer, Server


def disable_sdk_tracing(server: Server[Any] | MCPServer) -> None:
    """Remove the SDK's tracing middleware from this server instance.

    Requires the MCP SDK extra. Other middleware, including request-state
    security, is preserved. Global OpenTelemetry providers and environment
    variables are unchanged. This does not control outbound client tracing
    or instrumentation installed separately by the host application.
    """
    from mcp.server._otel import OpenTelemetryMiddleware

    server.middleware[:] = [
        middleware
        for middleware in server.middleware
        if not isinstance(middleware, OpenTelemetryMiddleware)
    ]
