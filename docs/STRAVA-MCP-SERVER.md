# Strava MCP Server

This document describes a FastMCP server that exposes locally stored Strava data to Claude Desktop.

The MCP server should be read-only against Strava data. It should query Postgres and return Claude-friendly summaries. It should not call Strava directly for normal tool execution.

## Goals

- Let Claude answer questions about training history using local Postgres data.
- Avoid sending raw multi-hour streams into the model context.
- Keep the current FastAPI app behavior unchanged.
- Secure remote MCP access from the VPS.
- Use Claude Desktop's local MCP process model to bridge to the remote server.

## Process Model

Recommended deployment shape:

```mermaid
flowchart TD
    claude[Claude Desktop] --> proxy[Local MCP Proxy Process]
    proxy -->|"HTTPS SSE with token"| nginx[Host Nginx]
    nginx --> mcp[FastMCP Server]
    mcp --> postgres[(Postgres)]
    api[Existing FastAPI App] --> postgres
```

The existing FastAPI app continues to handle webhooks, OAuth, dashboard APIs, and Telegram automation.

The MCP server can be either:

- A separate Python process/container that shares the same Postgres database.
- A mounted sub-app inside FastAPI, if FastMCP and deployment constraints make that simpler.

Prefer a separate process once the server is exposed over SSE. It keeps MCP concerns isolated from the existing app.

## Package And Runtime

Add FastMCP only when implementation begins. Do not add it just for documentation.

Expected future backend dependency:

```text
fastmcp
```

Possible file layout:

```text
backend/
  app/
    mcp/
      __init__.py
      server.py
      analysis.py
      queries.py
      auth.py
```

`queries.py` should contain Postgres read helpers. `analysis.py` should contain stream aggregation and derived metrics. `server.py` should define MCP tools.

## Security

The SSE endpoint must not be public without authentication.

The PoC uses per-user API keys generated from the web UI. Only a hash of each key is stored in Postgres, and the raw key is shown once when generated.

Recommended HTTP header:

```text
Authorization: Bearer <generated_mcp_api_key>
```

Use `Authorization: Bearer` consistently so clients and nginx only need to forward the standard authorization header.

Security requirements:

- Store only hashed API keys.
- Scope every query to the API key owner's connected Strava athlete ID.
- Reject missing or invalid tokens with `401`.
- Serve only over HTTPS in production.
- Keep the MCP server read-only for the first implementation.
- Do not expose token values in logs.

## SSE Transport

FastMCP can run with SSE transport:

```python
from fastmcp import FastMCP

mcp = FastMCP("strava-analytics")

@mcp.tool()
async def search_activities(query: str) -> str:
    ...

if __name__ == "__main__":
    mcp.run(transport="sse")
```

Expose it under a stable route such as:

```text
/mcp/sse
```

If the MCP server runs as a separate container, nginx can route `/mcp/` to that container and `/api/` to the existing FastAPI container.

## Claude Desktop Proxy

Claude Desktop starts local binaries for MCP servers. To reach the VPS-hosted SSE endpoint, use a local proxy process.

Example `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "strava-vps": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/proxy-server",
        "https://strava.andrewallkin.cloud/mcp/sse"
      ],
      "env": {
        "HTTP_HEADERS": "{\"Authorization\": \"Bearer your_generated_mcp_api_key\"}"
      }
    }
  }
}
```

Keep the real key out of the repository.

## Nginx Routing

Example production routing:

```nginx
location /mcp/ {
    proxy_pass http://127.0.0.1:8003/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Authorization $http_authorization;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 3600s;
}
```

SSE connections are long-lived, so buffering should be disabled for the MCP route.

The existing `/api/` and frontend routes from `docs/VPS-DEPLOYMENT.md` should remain unchanged. A separate MCP subdomain is not required for the PoC; path-based routing under the existing `strava.andrewallkin.cloud` certificate is enough.

## Tool Design Principles

MCP tools should return bounded, useful text. They should not dump raw JSON unless the tool is explicitly for debugging.

Good tool behavior:

- Accept narrow inputs such as date ranges, activity IDs, or activity types.
- Query scalar columns first.
- Load streams only when required.
- Downsample streams before returning results.
- Include assumptions in the response, such as heart-rate zone thresholds.
- Return plain-language summaries plus compact structured metrics.

Avoid:

- Returning full `stream_data` for long activities.
- Calling Strava APIs during tool execution.
- Mutating Strava activity data.
- Exposing OAuth tokens or raw secrets.

## Suggested Tools

### `search_activities`

Find activities by date range, type, name, distance, duration, or metadata.

Example signature:

```python
@mcp.tool()
async def search_activities(
    start_date: str | None = None,
    end_date: str | None = None,
    sport_type: str | None = None,
    limit: int = 20,
) -> str:
    """Search locally ingested Strava activities."""
```

Return fields:

- Activity ID.
- Date.
- Name.
- Sport type.
- Distance.
- Moving time.
- Elevation.
- Average heart rate if available.

### `get_activity_summary`

Return a compact summary for one activity.

Include:

- Basic metrics.
- Gear.
- Splits if present in `summary_data`.
- Stream availability.
- Derived metadata.

Do not include raw streams.

### `get_workout_analysis`

Analyze one activity using streams.

Useful output:

- Pace or speed consistency.
- Heart-rate zones.
- Heart-rate drift.
- Power summary if watts are available.
- Cadence summary if cadence is available.
- Notable missing data.

### `get_weekly_training_summary`

Summarize training over a week or custom date range.

Useful output:

- Total distance.
- Total moving time.
- Elevation.
- Activity count by sport.
- Longest activity.
- Hardest activity by available metric.
- Distribution by heart-rate zone if enough data exists.

### `compare_periods`

Compare two date ranges.

Useful output:

- Volume change.
- Intensity change.
- Long-run or long-ride change.
- Recovery or rest day count.
- Caveats when data is incomplete.

### `get_downsampled_streams`

Return downsampled streams for one activity.

Parameters:

- `activity_id`
- `bucket_seconds`, default `60`
- `streams`, default `["distance", "altitude", "heartrate", "velocity_smooth", "watts"]`

Return one row per time bucket, not one row per raw sample.

## Downsampling Strategy

Raw Strava streams often have one point per second. A 4-hour ride can have more than 14,000 samples per stream.

Recommended downsampling:

- Bucket by elapsed time, usually 60 seconds.
- For each bucket, calculate averages for continuous values.
- For distance, keep start and end distance.
- For location, return a representative point only when needed.
- Include sample counts per bucket to show data quality.

Example compact output:

```text
Activity 123456789, 60-second buckets:
- 00:00-01:00: distance 0.23 km, avg HR 128, avg speed 13.8 km/h
- 01:00-02:00: distance 0.25 km, avg HR 132, avg speed 15.0 km/h
```

## Heart-Rate Zones

Heart-rate analysis should document its assumptions.

Initial options:

- Use fixed zones configured in environment variables.
- Store zones in a future user settings table.
- Calculate approximate zones from max heart rate if available.

Recommended first version:

- Add explicit configuration for zone boundaries.
- Return a warning when heart-rate data or zones are missing.

Example:

```text
Zones used: Z1 < 120, Z2 120-139, Z3 140-154, Z4 155-169, Z5 >= 170 bpm.
```

## Read-Only Database Access

The MCP server should use a database user with read-only permissions if possible.

Minimum required tables:

- `strava_activities`
- `strava_activity_streams`
- `strava_ingestion_jobs` for ingestion status tools, if exposed.
- `strava_backfill_runs` for backfill status tools, if exposed.

Do not grant write permissions unless a future tool explicitly needs them.

## Testing Strategy

Run tests inside Docker.

Recommended coverage:

- Tool functions return bounded output for long streams.
- Activities marked deleted are excluded by default.
- Tools handle missing stream keys gracefully.
- Auth middleware rejects missing and invalid tokens.
- MCP queries never call Strava APIs.
- Existing FastAPI webhook and UI tests still pass.

## Failure Modes

Expected failures and responses:

- Missing activity ID: return a clear not-found message.
- Missing streams: return summary data and say streams were not ingested.
- Incomplete backfill: disclose that data may be partial.
- Invalid date range: return validation error.
- Database unavailable: fail the tool with a concise operational error.

Do not expose stack traces, tokens, or raw connection strings in tool responses.
