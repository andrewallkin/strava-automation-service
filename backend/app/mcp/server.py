from __future__ import annotations

import logging

from fastmcp import FastMCP
from fastmcp.server.auth.providers.debug import DebugTokenVerifier

from app.config import get_settings
from app.db import SessionLocal
from app.mcp.auth import McpAuthError, require_mcp_user
from app.mcp.formatting import format_activity_detail, format_activity_list
from app.mcp.queries import get_user_activity, list_user_activities
from app.services.mcp_api_key_service import is_valid_mcp_api_key

log = logging.getLogger("mcp")
mcp = FastMCP(
    "strava-automation-service",
    auth=DebugTokenVerifier(
        validate=is_valid_mcp_api_key,
        client_id="strava-automation-service",
        scopes=["activities:read"],
    ),
)


@mcp.tool()
def list_activities(
    start_date: str | None = None,
    end_date: str | None = None,
    sport_type: str | None = None,
    limit: int = 20,
) -> str:
    """List locally ingested Strava activities for the authenticated user."""
    try:
        user = require_mcp_user()
        with SessionLocal() as db:
            rows = list_user_activities(
                db,
                user,
                start_date=start_date,
                end_date=end_date,
                sport_type=sport_type,
                limit=limit,
            )
        return format_activity_list(rows)
    except McpAuthError as exc:
        return f"Authentication failed: {exc}"
    except ValueError as exc:
        return f"Invalid request: {exc}"
    except Exception:
        log.exception("MCP list_activities failed")
        return "Unable to list activities due to an internal service error."


@mcp.tool()
def get_activity(activity_id: int) -> str:
    """Get one locally ingested Strava activity for the authenticated user."""
    try:
        user = require_mcp_user()
        with SessionLocal() as db:
            activity, metrics = get_user_activity(db, user, activity_id)
        if not activity:
            return "Activity not found for the authenticated user."
        return format_activity_detail(activity, metrics)
    except McpAuthError as exc:
        return f"Authentication failed: {exc}"
    except Exception:
        log.exception("MCP get_activity failed")
        return "Unable to get activity due to an internal service error."


if __name__ == "__main__":
    settings = get_settings()
    mcp.run(transport="sse", host=settings.app_host, port=settings.app_port)
