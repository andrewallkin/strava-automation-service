from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.external_errors import ExternalAPIError
from app.models import User
from app.services.external_activities import (
    activity_detail,
    athlete_payload,
    best_efforts_payload,
    health_payload,
    laps_payload,
    list_activities,
    splits_payload,
    stat_activities_between,
    zones_payload,
)
from app.services.external_api_key_service import authenticate_external_api_key
from app.services.external_stats import JOHANNESBURG, consistency, local_today, range_periods, rollup, weekly_periods

router = APIRouter(prefix="/api/external", tags=["external"])
_bearer = HTTPBearer(auto_error=False)
_DOCS = Path(__file__).resolve().parents[2] / "docs" / "external-strava-api.md"


def require_external_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise ExternalAPIError(401, "unauthorized", "Missing API key")
    user = authenticate_external_api_key(db, credentials.credentials)
    if user is None:
        raise ExternalAPIError(401, "unauthorized", "Invalid or missing API key")
    return user


def _parse_date(value: str | None, field: str) -> date | None:
    if value is None or value == "":
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError as exc:
        raise ExternalAPIError(422, "invalid_query", f"{field} must be an ISO date") from exc


@router.get("/docs", response_class=PlainTextResponse)
def external_docs() -> PlainTextResponse:
    if not _DOCS.is_file():
        raise ExternalAPIError(404, "not_found", "External API documentation not found")
    return PlainTextResponse(_DOCS.read_text(encoding="utf-8"), media_type="text/markdown; charset=utf-8")


@router.get("/health")
def external_health(db: Session = Depends(get_db), user: User = Depends(require_external_user)) -> dict:
    return health_payload(db, user)


@router.get("/athlete")
def external_athlete(db: Session = Depends(get_db), user: User = Depends(require_external_user)) -> dict:
    return athlete_payload(db, user)


@router.get("/activities")
def external_activities(
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
    db: Session = Depends(get_db),
    user: User = Depends(require_external_user),
) -> dict:
    if typeGroup is not None and typeGroup not in {"run", "strength", "other"}:
        raise ExternalAPIError(422, "invalid_query", "typeGroup must be run, strength, or other")
    if sort not in {"start_date_desc", "start_date_asc"}:
        raise ExternalAPIError(422, "invalid_query", "sort must be start_date_desc or start_date_asc")
    if page < 1:
        raise ExternalAPIError(422, "invalid_query", "page must be at least 1")
    if perPage < 1 or perPage > 100:
        raise ExternalAPIError(422, "invalid_query", "perPage must be between 1 and 100")
    return list_activities(
        db,
        user,
        after=_parse_date(after, "after"),
        before=_parse_date(before, "before"),
        sport=sport,
        type_group_name=typeGroup,
        min_distance_m=minDistanceM,
        max_distance_m=maxDistanceM,
        min_moving_time_sec=minMovingTimeSec,
        max_moving_time_sec=maxMovingTimeSec,
        has_heartrate=hasHeartrate,
        gear_id=gearId,
        trainer=trainer,
        page=page,
        per_page=perPage,
        sort=sort,
    )


@router.get("/activities/{activity_id}")
def external_activity(
    activity_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_external_user),
) -> dict:
    return activity_detail(db, user, activity_id)


@router.get("/activities/{activity_id}/laps")
def external_laps(activity_id: int, db: Session = Depends(get_db), user: User = Depends(require_external_user)) -> dict:
    return laps_payload(db, user, activity_id)


@router.get("/activities/{activity_id}/splits")
def external_splits(activity_id: int, db: Session = Depends(get_db), user: User = Depends(require_external_user)) -> dict:
    return splits_payload(db, user, activity_id)


@router.get("/activities/{activity_id}/zones")
def external_zones(activity_id: int, db: Session = Depends(get_db), user: User = Depends(require_external_user)) -> dict:
    return zones_payload(db, user, activity_id)


@router.get("/activities/{activity_id}/best-efforts")
def external_best_efforts(
    activity_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_external_user),
) -> dict:
    return best_efforts_payload(db, user, activity_id)


@router.get("/stats/weekly")
def external_weekly(
    weeks: int = 8,
    db: Session = Depends(get_db),
    user: User = Depends(require_external_user),
) -> dict:
    if weeks < 1 or weeks > 26:
        raise ExternalAPIError(422, "invalid_query", "weeks must be between 1 and 26")
    today = local_today()
    periods = weekly_periods(weeks, today)
    load_start, _ = range_periods_start(periods)
    activities = stat_activities_between(db, user, load_start, periods[-1][1])
    return {"timezone": str(JOHANNESBURG), "weeks": rollup(activities, periods, "week")}


@router.get("/stats/range")
def external_range(
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
    groupBy: str = "week",
    db: Session = Depends(get_db),
    user: User = Depends(require_external_user),
) -> dict:
    start = _parse_date(from_, "from")
    end = _parse_date(to, "to")
    if start is None or end is None:
        raise ExternalAPIError(422, "invalid_query", "from and to are required")
    if end < start:
        raise ExternalAPIError(422, "invalid_query", "to must be on or after from")
    if groupBy not in {"day", "week", "month"}:
        raise ExternalAPIError(422, "invalid_query", "groupBy must be day, week, or month")
    periods = range_periods(start, end, groupBy)
    previous_start, _previous_end = periods[0]
    from app.services.external_stats import previous_window

    load_start, _ = previous_window(previous_start, periods[0][1], groupBy)
    activities = stat_activities_between(db, user, load_start, end)
    return {"timezone": str(JOHANNESBURG), "groupBy": groupBy, "periods": rollup(activities, periods, groupBy)}


@router.get("/stats/consistency")
def external_consistency(db: Session = Depends(get_db), user: User = Depends(require_external_user)) -> dict:
    today = local_today()
    activities = stat_activities_between(db, user, today.fromordinal(today.toordinal() - 27), today)
    return consistency(activities, today)


def range_periods_start(periods: list[tuple[date, date]]) -> tuple[date, date]:
    from app.services.external_stats import previous_window

    return previous_window(periods[0][0], periods[0][1], "week")
