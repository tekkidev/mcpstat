# Latency Tracking

Track execution duration for tool calls to identify slow tools and monitor performance.

---

## Overview

Latency tracking measures how long each tool takes to execute. This enables:

- **Performance monitoring** - Identify slow tools affecting user experience
- **SLA compliance** - Ensure tools meet response time requirements
- **Optimization targets** - Focus engineering effort on slow tools
- **Trend analysis** - Detect performance degradation over time

---

## Basic Usage (Recommended)

Use the `@stat.track` decorator for automatic latency tracking:

```python
from mcp.server import Server
from mcpstat import MCPStat

app = Server("my-server")
stat = MCPStat("my-server")

@app.call_tool()
@stat.track  # ← Automatic latency tracking!
async def handle_tool(name: str, arguments: dict):
    return await my_logic(arguments)
```

That's it! The decorator automatically:

- Measures execution time
- Records call count
- Tracks success/failure
- Never crashes your code

---

## Context Manager Alternative

For more control, use the `tracking` context manager:

```python
async def handle_tool(name: str, arguments: dict):
    async with stat.tracking(name, "tool"):
        result = await my_logic(arguments)
        return result
```

---

## Manual Recording (Advanced)

If you need to pass additional data (tokens, response size), use `record()` directly:

```python
import time

@app.call_tool()
async def handle_tool(name: str, arguments: dict):
    start = time.perf_counter()
    result = await my_logic(arguments)
    duration_ms = int((time.perf_counter() - start) * 1000)

    await stat.record(
        name, "tool",
        duration_ms=duration_ms,
        response_chars=len(str(result))
    )
    return result
```

---

## Latency Statistics

`get_stats()` includes comprehensive latency information:

```python
stats = await stat.get_stats()
```

### Response Structure

```python
{
    "latency_summary": {
        "total_duration_ms": 15000,    # Sum across all tools
        "has_latency_data": True       # True if any duration recorded
    },
    "stats": [
        {
            "name": "my_tool",
            "call_count": 10,
            "total_duration_ms": 5000,  # Total time spent
            "min_duration_ms": 100,     # Fastest call
            "max_duration_ms": 1200,    # Slowest call
            "avg_latency_ms": 500,      # Average per call
            ...
        }
    ]
}
```

### Latency Fields

| Field | Description |
|-------|-------------|
| `total_duration_ms` | Cumulative execution time in milliseconds |
| `min_duration_ms` | Fastest recorded execution (NULL if no data) |
| `max_duration_ms` | Slowest recorded execution (NULL if no data) |
| `avg_latency_ms` | Average duration per call |

---

## Use Cases

### Identifying Slow Tools

Find tools with the highest average latency:

```python
stats = await stat.get_stats()

# Sort by average latency
by_latency = sorted(
    [s for s in stats["stats"] if s["avg_latency_ms"] > 0],
    key=lambda s: s["avg_latency_ms"],
    reverse=True
)

print("Slowest tools:")
for tool in by_latency[:5]:
    print(f"  {tool['name']}: {tool['avg_latency_ms']}ms avg")
```

### Performance Alerts

Set up warnings for slow tools:

```python
stats = await stat.get_stats()
SLA_THRESHOLD_MS = 1000  # 1 second

for tool in stats["stats"]:
    if tool["max_duration_ms"] and tool["max_duration_ms"] > SLA_THRESHOLD_MS:
        print(f"⚠️ {tool['name']}: max latency {tool['max_duration_ms']}ms exceeds SLA")
```

### Total Time Analysis

Track total server time spent in tool execution:

```python
stats = await stat.get_stats()
summary = stats["latency_summary"]

print(f"Total execution time: {summary['total_duration_ms'] / 1000:.1f}s")

# Per-tool breakdown
for tool in stats["stats"]:
    if tool["total_duration_ms"] > 0:
        pct = tool["total_duration_ms"] / summary["total_duration_ms"] * 100
        print(f"  {tool['name']}: {pct:.1f}% of total time")
```

### Variance Analysis

Identify tools with inconsistent performance:

```python
for tool in stats["stats"]:
    if tool["min_duration_ms"] and tool["max_duration_ms"]:
        variance = tool["max_duration_ms"] - tool["min_duration_ms"]
        if variance > 500:  # More than 500ms variance
            print(f"⚠️ {tool['name']}: high variance ({tool['min_duration_ms']}-{tool['max_duration_ms']}ms)")
```

---

## Combined Tracking

Track both tokens and latency for comprehensive analytics:

```python
import time

@app.call_tool()
async def handle_tool(name: str, arguments: dict):
    start = time.perf_counter()
    result = await my_logic(arguments)
    duration_ms = int((time.perf_counter() - start) * 1000)

    await stat.record(
        name, "tool",
        response_chars=len(str(result)),
        duration_ms=duration_ms
    )
    return result
```

---

## Database Schema

Latency tracking adds these columns to `mcpstat_usage`:

| Column | Type | Description |
|--------|------|-------------|
| `total_duration_ms` | INTEGER | Cumulative execution time |
| `min_duration_ms` | INTEGER | Minimum recorded duration (nullable) |
| `max_duration_ms` | INTEGER | Maximum recorded duration (nullable) |

---

## Migration

!!! info "Since v0.2.2"
    Latency tracking columns were added in version 0.2.2. Existing databases are automatically migrated to include these columns. All existing data is preserved:

    - `total_duration_ms` defaults to `0`
    - `min_duration_ms` and `max_duration_ms` default to `NULL`

---

## Best Practices

### 1. Measure Full Execution Time

Include all processing time, not just external calls:

```python
start = time.perf_counter()
# Include validation, processing, serialization
result = await full_tool_logic(arguments)
duration_ms = int((time.perf_counter() - start) * 1000)
```

### 2. Use perf_counter for Accuracy

`time.perf_counter()` provides the highest resolution timer:

```python
# Good - high resolution, monotonic
start = time.perf_counter()

# Avoid - lower resolution, can jump
# start = time.time()
```

### 3. Set Performance Budgets

Define acceptable latency thresholds per tool type:

```python
BUDGETS = {
    "cache_lookup": 50,    # 50ms for cached data
    "api_call": 2000,      # 2s for external APIs
    "computation": 500,    # 500ms for local processing
}
```

### 4. Monitor Trends

Track latency over time to detect degradation:

```python
# Log periodic summaries
stats = await stat.get_stats()
for tool in stats["stats"]:
    if tool["call_count"] > 100:  # Enough data
        print(f"{tool['name']}: {tool['avg_latency_ms']}ms avg over {tool['call_count']} calls")
```
