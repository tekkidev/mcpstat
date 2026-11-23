# Configuration

Configure mcpstat via constructor arguments or environment variables.

---

## Constructor Options

```python
from mcpstat import MCPStat

stat = MCPStat(
    "my-server",
    db_path="./stats.sqlite",  # SQLite database path
    log_path="./usage.log",  # File log path
    log_enabled=True,  # Enable file logging
    metadata_presets={  # Pre-define tool metadata
        "my_tool": {"tags": ["api", "data"], "short": "Fetch data from API"}
    },
)
```

---

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `server_name` | `str` | Required | Identifier for your MCP server |
| `db_path` | `str` | `./mcp_stat_data.sqlite` | Path to SQLite database |
| `log_path` | `str` | `./mcp_stat.log` | Path to file log |
| `log_enabled` | `bool` | `False` | Enable timestamped file logging |
| `metadata_presets` | `dict` | `None` | Pre-defined metadata for tools |
| `cleanup_orphans` | `bool` | `True` | Deactivate unregistered tools in the catalog while retaining usage |

---

## Environment Variables

Environment variables override constructor arguments:

| Variable | Description |
|----------|-------------|
| `MCPSTAT_DB_PATH` | SQLite database path |
| `MCPSTAT_LOG_PATH` | Log file path |
| `MCPSTAT_LOG_ENABLED` | Enable logging (`true`, `1`, `yes`) |

```bash
export MCPSTAT_DB_PATH=./stats.sqlite
export MCPSTAT_LOG_PATH=./usage.log
export MCPSTAT_LOG_ENABLED=true
```

---

## SDK Tracing and Local Statistics

mcpstat records statistics in your SQLite database and configures no remote telemetry
exporter. Optional local file logging is disabled by default. The bundled server and
examples explicitly remove the MCP SDK's inbound OpenTelemetry tracing middleware.
Local usage, outcome, and latency statistics continue to work.

For an existing SDK v2 server, opt out of its inbound tracing after creating the app:

```python
from mcp.server import MCPServer
from mcpstat import disable_sdk_tracing

app = MCPServer("my-server")
disable_sdk_tracing(app)
```

The helper accepts `Server` and `MCPServer`. It preserves other middleware, including
request-state security, and does not change the host application's global tracing
provider or environment. Importing the core library does not import the MCP SDK.

To disable OpenTelemetry SDK signals for the entire server process, set these variables
in its MCP launch configuration before Python starts:

```json
{"env":{"OTEL_SDK_DISABLED":"true","OTEL_PROPAGATORS":"none"}}
```

`OTEL_SDK_DISABLED` does not disable propagation by itself; `OTEL_PROPAGATORS=none`
also disables the default trace-context and baggage propagators. The bundled command
sets both variables and disables already-initialized context propagators when it
starts. Its registry launch configuration also includes both variables. Configure
the launch environment when an auto-instrumentation
agent initializes before application code. The instance helper does not control
outbound SDK client spans or instrumentation installed separately by the host.

These settings affect SDK tracing, not mcpstat's local statistics. The documentation
website's consent-based Google Analytics is separate from the Python runtime.

---

## Metadata Presets

Pre-define tags and descriptions for tools:

```python
stat = MCPStat(
    "my-server",
    metadata_presets={
        "fetch_weather": {
            "tags": ["api", "weather", "external"],
            "short": "Fetch weather data from external API",
        },
        "parse_json": {"tags": ["utility", "parsing"], "short": "Parse JSON strings"},
    },
)
```

### Metadata Fields

| Field | Type | Description |
|-------|------|-------------|
| `tags` | `list[str]` | Categories for filtering |
| `short` | `str` | Brief description (one line) |

---

## Auto-Tag Extraction

When syncing MCP tools, tags are auto-derived from tool names:

```python
# Sync metadata from your MCP server's tools
tools = await list_tools()
await stat.sync_tools(tools)
```

Auto-extraction rules:

- Names split on `-` and `_`
- Normalized to lowercase
- Stopwords filtered (`the`, `to`, `from`, `and`, etc.)

Example: `fetch_weather_data` → `["fetch_weather_data", "fetch", "weather", "data"]`

---

## Manual Metadata Registration

Register metadata at runtime:

```python
await stat.register_metadata(
    "my_tool",
    tags=["api", "weather", "external"],
    short_description="Fetch weather data from external API",
)
```

---

## File Logging

When enabled, mcpstat writes a timestamped log:

```json
{"timestamp":"2026-02-01T10:30:45+00:00","type":"tool","name":"fetch_weather","outcome":"success"}
{"timestamp":"2026-02-01T10:30:46+00:00","type":"tool","name":"parse_json","outcome":"error"}
```

Useful for:

- Debugging agent behavior
- Detecting loops (repeated calls in short time)
- Local invocation history

JSON logs omit arguments, results, and exception text. Names and resource URIs can still
contain sensitive data. Files rotate at 5 MiB with three backups; give independent trackers
separate log paths. Local files are mutable and do not provide tamper-proof evidence.

---

## Database Schema

mcpstat uses SQLite with two tables:

### `mcpstat_usage`

| Column | Type | Description |
|--------|------|-------------|
| `name` | TEXT | Primitive name; part of the composite identity |
| `type` | TEXT | `tool`, `prompt`, or `resource` |
| `call_count` | INTEGER | Total invocations |
| `last_accessed` | TEXT | ISO 8601 timestamp |
| `created_at` | TEXT | ISO 8601 creation timestamp |
| `total_input_tokens` | INTEGER | Cumulative input tokens |
| `total_output_tokens` | INTEGER | Cumulative output tokens |
| `total_response_chars` | INTEGER | Cumulative response characters |
| `estimated_tokens` | INTEGER | Estimated from response size |
| `total_duration_ms` | INTEGER | Cumulative execution time |
| `min_duration_ms` | INTEGER | Minimum recorded duration (nullable) |
| `max_duration_ms` | INTEGER | Maximum recorded duration (nullable) |

### `mcpstat_metadata`

| Column | Type | Description |
|--------|------|-------------|
| `name` | TEXT | Primitive name; part of the composite identity |
| `tags` | TEXT | JSON array of normalized tags |
| `short_description` | TEXT | Brief description |
| `full_description` | TEXT | Extended description |
| `schema_version` | INTEGER | Schema version number |
| `updated_at` | TEXT | ISO 8601 last update timestamp |

---

## Best Practices

### 1. Single Instance

Create one `MCPStat` instance at module level:

```python
# ✅ Correct
stat = MCPStat("my-server")


async def handle_tool(name, args):
    await stat.record(name, "tool")
```

```python
# ❌ Wrong - creates new instance per call
async def handle_tool(name, args):
    stat = MCPStat("my-server")  # Don't do this
    await stat.record(name, "tool")
```

### 2. Use @stat.track Decorator (Recommended)

The `@stat.track` decorator is the simplest and most reliable tracking method:

```python
# ✅ Recommended - automatic latency tracking, never misses a call


@stat.track
async def handle_tool(name: str, arguments: dict):
    return await my_logic(arguments)
```

For manual instrumentation, use the context manager to preserve exception and cancellation behavior:

```python
async def handle_tool(name, args):
    async with stat.tracking(name, "tool"):
        return await my_logic(args)
```

Call `record()` once after execution when supplying explicit measurements and outcomes.

### 3. Use Environment Variables in Production

```bash
# docker-compose.yml
services:
  mcp-server:
    environment:
      - MCPSTAT_DB_PATH=/data/stats.sqlite
      - MCPSTAT_LOG_ENABLED=true
```

## Storage identity and lifecycle

Both tables use `(server, type, name)` as their primary key. The `server` column scopes
records to `server_name`; resources use their full URI. Metadata includes an `active`
flag, and synchronization deactivates missing tools without deleting usage history or
other primitive metadata. Usage includes outcome counters and `duration_sample_count`.

Opening an older unscoped database assigns its records to the first server that opens it.
Back up the database before upgrading or changing server identities. The schema cannot
recover identities that older versions already merged. Historical latency with an unknown
sample count retains totals and extrema but reports an unknown average.

The library defaults to the configured working-directory paths. The runnable server uses
the platform user data directory unless environment variables override it. Memory databases
are not supported. Restrict access to the directory and authorize analytics tools in the
host server. Keep tenant identities separate when sharing a database.

SQLite operations execute in worker threads. Lock waits are bounded; storage failures can
lose measurements and are reported to stderr without exception text. An already submitted
transaction can finish after its awaiting task is cancelled. Close the tracker after
outstanding handlers finish. The owner controls database retention.

## Upgrading from 0.2.x

The core `MCPStat` recording and query methods remain available, but 0.3.0 is not a
fully interchangeable upgrade. Back up the database with active writers stopped, keep
the same `server_name`, and allow the first operation to migrate the file. Migration
assigns older unscoped records to that first server name. It cannot reconstruct names
or types already merged by an older version. To return to an older package version,
restore the pre-upgrade backup; the older schema is not maintained alongside the new one.

The `mcp` and `server` extras install MCP SDK >=2.3,<3. An application using SDK v1
registration decorators needs the constructor adapters in the [quick start](quickstart.md),
or the SDK v2 `MCPServer` tool API. Installing the SDK-independent core alone does not
require replacing the host server's SDK. The Python minimum remains 3.10.

Check integrations that parse log lines (now JSON), use zero/negative or unbounded query
limits, label prompts with a period other than `all time`, use resource display names
instead of full URIs, or assume every latency average is numeric. Counts of measured calls
now determine averages. Catalog synchronization retains historical usage and only active
tools appear in the catalog. Applications that previously used the catalog to retrieve
prompt/resource metadata should use `get_stats(type_filter=...)`.
