from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastmcp import FastMCP

from app.db import SessionLocal
from app.external_errors import ExternalAPIError
from app.mcp.auth import McpAuthError, require_mcp_user
from app.routers.external import (
    external_activities,
    external_activity,
    external_athlete,
    external_best_efforts,
    external_consistency,
    external_health,
    external_laps,
    external_range,
    external_splits,
    external_weekly,
    external_zones,
)

READ_ONLY = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "openWorldHint": False,
    "idempotentHint": True,
}


def invoke_external(operation: Callable[..., dict], **kwargs: Any) -> dict:
    """Call one external API route function and return its JSON body."""
    try:
        user = require_mcp_user()
        with SessionLocal() as db:
            return operation(db=db, user=user, **kwargs)
    except McpAuthError as exc:
        return {"error": {"code": "unauthorized", "message": str(exc)}}
    except ExternalAPIError as exc:
        return {"error": {"code": exc.code, "message": exc.message}}


def health() -> dict:
    """Same payload as GET /api/external/health."""
    return invoke_external(external_health)


def athlete() -> dict:
    """Same payload as GET /api/external/athlete."""
    return invoke_external(external_athlete)


def list_activities(
    after: str | None = None,
    before: str | None = None,
    sport: str | None = None,
    typeGroup: str | None = None,
    minDistanceM: float | None = None,
    maxDistanceM: float | None = None,
    minMovingTimeSec: int | None = None,
    maxMovingTimeSec: int | None = None,
    hasHeartrate: bool | None = None,
    gearId: str | None = None,
    trainer: bool | None = None,
    page: int = 1,
    perPage: int = 30,
    sort: str = "start_date_desc",
) -> dict:
    """Same payload as GET /api/external/activities. Filters use the external API names."""
    return invoke_external(
        external_activities,
        after=after,
        before=before,
        sport=sport,
        typeGroup=typeGroup,
        minDistanceM=minDistanceM,
        maxDistanceM=maxDistanceM,
        minMovingTimeSec=minMovingTimeSec,
        maxMovingTimeSec=maxMovingTimeSec,
        hasHeartrate=hasHeartrate,
        gearId=gearId,
        trainer=trainer,
        page=page,
        perPage=perPage,
        sort=sort,
    )


def get_activity(activity_id: int) -> dict:
    """Same payload as GET /api/external/activities/{id}."""
    return invoke_external(external_activity, activity_id=activity_id)


def get_activity_laps(activity_id: int) -> dict:
    """Same payload as GET /api/external/activities/{id}/laps."""
    return invoke_external(external_laps, activity_id=activity_id)


def get_activity_splits(activity_id: int) -> dict:
    """Same payload as GET /api/external/activities/{id}/splits."""
    return invoke_external(external_splits, activity_id=activity_id)


def get_activity_zones(activity_id: int) -> dict:
    """Same payload as GET /api/external/activities/{id}/zones."""
    return invoke_external(external_zones, activity_id=activity_id)


def get_activity_best_efforts(activity_id: int) -> dict:
    """Same payload as GET /api/external/activities/{id}/best-efforts."""
    return invoke_external(external_best_efforts, activity_id=activity_id)


def stats_weekly(weeks: int = 8) -> dict:
    """Same payload as GET /api/external/stats/weekly."""
    return invoke_external(external_weekly, weeks=weeks)


def stats_range(from_date: str, to: str, groupBy: str = "week") -> dict:
    """Same payload as GET /api/external/stats/range. from_date is the external query parameter from."""
    return invoke_external(external_range, from_=from_date, to=to, groupBy=groupBy)


def stats_consistency() -> dict:
    """Same payload as GET /api/external/stats/consistency."""
    return invoke_external(external_consistency)


def register_external_tools(mcp: FastMCP) -> None:
    tools = [
        health,
        athlete,
        list_activities,
        get_activity,
        get_activity_laps,
        get_activity_splits,
        get_activity_zones,
        get_activity_best_efforts,
        stats_weekly,
        stats_range,
        stats_consistency,
    ]
    for tool in tools:
        mcp.tool(annotations=READ_ONLY)(tool)
