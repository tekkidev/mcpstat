# Token Tracking

Track response sizes and estimate token usage for cost analysis.

---

## Overview

MCP servers don't have direct access to LLM token counts - tokens are returned to the client, not the server. mcpstat provides both:

1. **Server-side estimation** - Estimate tokens from response character count
2. **Client-side injection** - Report actual tokens from LLM API responses

---

## Basic Usage (Estimation)

Track response sizes for automatic token estimation:

```python
@app.call_tool()
async def handle_tool(name: str, arguments: dict):
    result = await my_logic(arguments)

    # Record with response size for token estimation
    await stat.record(
        name, "tool",
        response_chars=len(str(result))
    )
    return result
```

mcpstat estimates tokens using ~3.5 characters per token (conservative for mixed content).

---

## Actual Token Tracking

If you have access to actual token counts from your LLM provider:

### Method 1: Record with Tokens

```python
await stat.record(
    name, "tool",
    input_tokens=100,
    output_tokens=250
)
```

### Method 2: Deferred Reporting

```python
# Record the call first
await stat.record("my_tool", "tool")

# Later, when tokens are available
response = await anthropic.messages.create(...)
await stat.report_tokens(
    "my_tool",
    response.usage.input_tokens,
    response.usage.output_tokens
)
```

---

## Token Statistics

`get_stats()` includes comprehensive token information:

```python
stats = await stat.get_stats()
```

### Response Structure

```python
{
    "token_summary": {
        "total_input_tokens": 5000,      # Sum across all tools
        "total_output_tokens": 12000,    # Sum across all tools
        "total_estimated_tokens": 3500,  # From response_chars
        "has_actual_tokens": True        # True if any actual tokens recorded
    },
    "stats": [
        {
            "name": "my_tool",
            "call_count": 10,
            "total_input_tokens": 1000,
            "total_output_tokens": 2500,
            "total_response_chars": 8000,
            "estimated_tokens": 2286,
            "avg_tokens_per_call": 350,   # (input + output) / calls
            ...
        }
    ]
}
```

### Token Fields

| Field | Description |
|-------|-------------|
| `total_input_tokens` | Cumulative input tokens (if tracked) |
| `total_output_tokens` | Cumulative output tokens (if tracked) |
| `total_response_chars` | Cumulative response characters |
| `estimated_tokens` | Tokens estimated from response size |
| `avg_tokens_per_call` | Average tokens per invocation |

---

## Estimation vs. Actual

mcpstat prioritizes actual tokens over estimates:

```python
# Priority for avg_tokens_per_call:
if total_input_tokens + total_output_tokens > 0:
    avg = (input + output) / call_count  # Use actual
else:
    avg = estimated_tokens / call_count  # Fall back to estimate
```

---

## Use Cases

### Cost Analysis

Track token usage to estimate API costs:

```python
stats = await stat.get_stats()
summary = stats["token_summary"]

total_tokens = summary["total_input_tokens"] + summary["total_output_tokens"]
estimated_cost = total_tokens * 0.00001  # Example rate
print(f"Estimated cost: ${estimated_cost:.4f}")
```

### Identifying Token-Heavy Tools

Find tools that consume the most tokens:

```python
stats = await stat.get_stats()

# Sort by total tokens
by_tokens = sorted(
    stats["stats"],
    key=lambda s: s["total_input_tokens"] + s["total_output_tokens"],
    reverse=True
)

for tool in by_tokens[:5]:
    total = tool["total_input_tokens"] + tool["total_output_tokens"]
    print(f"{tool['name']}: {total} tokens")
```

### Optimization Recommendations

```python
stats = await stat.get_stats()

for tool in stats["stats"]:
    avg = tool["avg_tokens_per_call"]
    if avg > 1000:
        print(f"⚠️ {tool['name']}: {avg} avg tokens/call - consider optimization")
```

---

## Database Schema

Token tracking adds these columns to `mcpstat_usage`:

| Column | Type | Description |
|--------|------|-------------|
| `total_input_tokens` | INTEGER | Cumulative input tokens |
| `total_output_tokens` | INTEGER | Cumulative output tokens |
| `total_response_chars` | INTEGER | Cumulative response characters |
| `estimated_tokens` | INTEGER | Tokens estimated from response size |

---

## Migration

!!! info "Since v0.2.1"
    Token tracking columns were added in version 0.2.1. Existing databases are automatically migrated to include these columns. All existing data is preserved, and new columns default to `0`.

---

## Best Practices

### 1. Track Response Sizes

Even without actual tokens, tracking response sizes provides useful estimates:

```python
await stat.record(
    name, "tool",
    response_chars=len(json.dumps(result))
)
```

### 2. Use Deferred Reporting for Accuracy

When actual tokens are available, use `report_tokens()`:

```python
# In your client code
response = await client.messages.create(...)
await stat.report_tokens(
    tool_name,
    response.usage.input_tokens,
    response.usage.output_tokens
)
```

### 3. Monitor High-Token Tools

Regularly check for tools with high average token usage:

```python
for tool in stats["stats"]:
    if tool["avg_tokens_per_call"] > 500:
        print(f"Review: {tool['name']}")
```
