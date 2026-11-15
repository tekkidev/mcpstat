"""
mcpstat - Usage tracking and analytics for MCP servers.
https://github.com/tekkidev/mcpstat

Copyright (c) 2026 Vadim Bakhrenkov
SPDX-License-Identifier: MIT

Verify scoped SDK tracing controls and real protocol behavior with tracing configured.
"""

from __future__ import annotations

import json
import sys

import pytest
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from mcp.server import MCPServer, Server
from mcp.server._otel import OpenTelemetryMiddleware
from opentelemetry import trace

from mcpstat import disable_sdk_tracing


@pytest.mark.parametrize("factory", [Server, MCPServer])
def test_disable_tracing_preserves_other_middleware(factory, monkeypatch):
    """Disabling one instance preserves security, custom middleware, and global state."""
    monkeypatch.setenv("OTEL_SDK_DISABLED", "false")
    app = factory("scoped-tracing")
    other = factory("other-server")

    async def custom(ctx, call_next):
        return await call_next(ctx)

    app.middleware.append(custom)
    expected = [m for m in app.middleware if not isinstance(m, OpenTelemetryMiddleware)]
    provider = trace.get_tracer_provider()
    disable_sdk_tracing(app)
    disable_sdk_tracing(app)
    assert app.middleware == expected
    assert app.middleware[-1] is custom
    if factory is MCPServer:
        assert len(expected) > 1  # The request-state security middleware remains.
    assert any(isinstance(m, OpenTelemetryMiddleware) for m in other.middleware)
    assert trace.get_tracer_provider() is provider
    import os

    assert os.environ["OTEL_SDK_DISABLED"] == "false"


_TRACED_SERVER = """
import json
import os
from contextlib import contextmanager
from pathlib import Path
from opentelemetry import trace

spans = []

class RecordingTracer(trace.NoOpTracer):
    @contextmanager
    def start_as_current_span(self, name, *args, **kwargs):
        spans.append(name)
        with super().start_as_current_span(name, *args, **kwargs) as span:
            yield span

class RecordingProvider(trace.NoOpTracerProvider):
    def get_tracer(self, *args, **kwargs):
        return RecordingTracer()

provider = RecordingProvider()
trace.set_tracer_provider(provider)
from mcpstat import server
if os.environ["TEST_TRACING"] == "enabled":
    from mcp.server._otel import OpenTelemetryMiddleware
    server.app.middleware.insert(0, OpenTelemetryMiddleware())
try:
    server.main()
finally:
    assert trace.get_tracer_provider() is provider
    with trace.get_tracer("host").start_as_current_span("host.application"):
        pass
    Path(os.environ["TEST_REPORT"]).write_text(json.dumps(spans))
"""


@pytest.mark.asyncio
@pytest.mark.parametrize("tracing", ["enabled", "disabled"])
@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_protocol_tracing_opt_out(tmp_path, tracing, mode):
    """A configured provider sees no server spans after opt-out; statistics still work."""
    report = tmp_path / "spans.json"
    params = StdioServerParameters(
        command=sys.executable,
        args=["-c", _TRACED_SERVER],
        env={
            "MCPSTAT_DB_PATH": str(tmp_path / "stats.sqlite"),
            "MCPSTAT_LOG_ENABLED": "false",
            "TEST_REPORT": str(report),
            "TEST_TRACING": tracing,
        },
    )
    async with Client(params, mode=mode) as client:
        await client.list_tools()
        result = await client.call_tool("celsius_to_fahrenheit", {"celsius": 100})
        assert result.structured_content["fahrenheit"] == 212
        stats = (await client.call_tool("get_tool_usage_stats", {})).structured_content
        row = next(r for r in stats["stats"] if r["name"] == "celsius_to_fahrenheit")
        assert row["call_count"] == row["success_count"] == row["duration_sample_count"] == 1
    spans = json.loads(report.read_text())
    assert spans.count("host.application") == 1
    sdk_spans = [name for name in spans if name != "host.application"]
    assert bool(sdk_spans) is (tracing == "enabled")
