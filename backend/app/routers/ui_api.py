import json
from datetime import date, timedelta
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_jwt_user
from app.models import EventLog, PendingActivity, User
from app.services.activity_service import include_gear_in_shoe_vault, list_gear
from app.services.external_activities import list_activities, stat_activities_between
from app.services.external_api_key_service import assign_external_api_key, revoke_external_api_key
from app.services.external_stats import by_sport_type, local_today, monday_on_or_before
from app.services.mcp_api_key_service import create_mcp_api_key, list_mcp_api_keys, revoke_mcp_api_key
from app.services.strava_service import StravaService
from app.services.webhook_processor import process_activity

router = APIRouter(prefix="/api/ui", tags=["ui"])


class SettingsUpdate(BaseModel):
    run_shoe_enabled: bool | None = None
    gym_hide_enabled: bool | None = None


class McpApiKeyCreate(BaseModel):
    name: str | None = None


class StravaExplorerRequest(BaseModel):
    method: Literal["GET", "POST", "PUT", "DELETE"] = "GET"
    endpoint: str
    params: dict[str, Any] | None = None
    body: Any | None = None
    body_encoding: Literal["json", "form"] = "json"


@router.get("/status")
def status(
    user: User = Depends(require_jwt_user),
) -> dict:
    return {
        "connected": bool(user.strava_athlete_id),
        "strava_athlete_id": user.strava_athlete_id,
        "athlete_name": user.athlete_name,
        "athlete_profile_url": user.athlete_profile_url,
        "run_shoe_enabled": user.run_shoe_enabled,
        "gym_hide_enabled": user.gym_hide_enabled,
    }


@router.post("/strava-explorer")
def strava_explorer(
    body: StravaExplorerRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_jwt_user),
) -> dict:
    if not user.access_token:
        raise HTTPException(status_code=404, detail="No user connected")
    strava = StravaService()
    return strava.explore_api(
        db,
        user,
        method=body.method,
        endpoint=body.endpoint,
        params=body.params,
        body=body.body,
        body_encoding=body.body_encoding,
    )


@router.patch("/settings")
def update_settings(
    body: SettingsUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_jwt_user),
) -> dict:
    if body.run_shoe_enabled is not None:
        user.run_shoe_enabled = body.run_shoe_enabled
    if body.gym_hide_enabled is not None:
        user.gym_hide_enabled = body.gym_hide_enabled
    db.commit()
    db.refresh(user)
    return {
        "run_shoe_enabled": user.run_shoe_enabled,
        "gym_hide_enabled": user.gym_hide_enabled,
    }


def _mcp_api_key_row(row, include_secret: str | None = None) -> dict:
    data = {
        "id": row.id,
        "name": row.name,
        "key_prefix": row.key_prefix,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
        "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
    }
    if include_secret is not None:
        data["api_key"] = include_secret
    return data


@router.get("/mcp-api-keys")
def mcp_api_keys(
    db: Session = Depends(get_db),
    user: User = Depends(require_jwt_user),
) -> list[dict]:
    return [_mcp_api_key_row(row) for row in list_mcp_api_keys(db, user)]


@router.post("/mcp-api-keys")
def create_mcp_key(
    body: McpApiKeyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_jwt_user),
) -> dict:
    if not user.strava_athlete_id:
        raise HTTPException(status_code=404, detail="No connected Strava user")
    created = create_mcp_api_key(db, user, name=body.name)
    return _mcp_api_key_row(created.row, include_secret=created.raw_key)


@router.delete("/mcp-api-keys/{key_id}")
def revoke_mcp_key(
    key_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_jwt_user),
) -> dict:
    if not revoke_mcp_api_key(db, user, key_id):
        raise HTTPException(status_code=404, detail="MCP API key not found")
    return {"revoked": True}


@router.get("/external-api-key")
def external_api_key_status(user: User = Depends(require_jwt_user)) -> dict:
    prefix = f"{user.external_api_key_prefix}..." if user.external_api_key_prefix else None
    created_at = user.external_api_key_created_at.isoformat() if user.external_api_key_created_at else None
    return {"has_key": bool(user.external_api_key_hash), "prefix": prefix, "created_at": created_at}


@router.post("/external-api-key")
def external_api_key_generate(
    db: Session = Depends(get_db),
    user: User = Depends(require_jwt_user),
) -> dict:
    raw_key = assign_external_api_key(db, user)
    return {
        "has_key": True,
        "api_key": raw_key,
        "prefix": f"{user.external_api_key_prefix}...",
        "created_at": user.external_api_key_created_at.isoformat() if user.external_api_key_created_at else None,
        "message": "Copy this key now. It will not be shown again.",
    }


@router.delete("/external-api-key")
def external_api_key_revoke(
    db: Session = Depends(get_db),
    user: User = Depends(require_jwt_user),
) -> dict:
    revoke_external_api_key(db, user)
    return {"has_key": False, "prefix": None, "created_at": None}


@router.get("/summary")
def summary(
    db: Session = Depends(get_db),
    _: User = Depends(require_jwt_user),
) -> dict:
    pending = len(db.scalars(select(PendingActivity)).all())
    latest = db.scalar(select(EventLog).order_by(EventLog.created_at.desc()).limit(1))
    runs_updated = db.scalar(
        select(func.count(EventLog.id)).where(
            EventLog.event_type == "run_action", EventLog.status == "ok"
        )
    ) or 0
    gym_hidden = db.scalar(
        select(func.count(EventLog.id)).where(
            EventLog.event_type == "gym_action", EventLog.status == "ok"
        )
    ) or 0
    return {
        "pending_count": pending,
        "last_event_at": (latest.created_at.isoformat() + "Z") if latest else None,
        "last_event_message": latest.message if latest else None,
        "runs_updated": runs_updated,
        "gym_hidden": gym_hidden,
    }


@router.get("/pending")
def pending(
    db: Session = Depends(get_db),
    _: User = Depends(require_jwt_user),
) -> list[dict]:
    rows = db.scalars(select(PendingActivity).order_by(PendingActivity.created_at.desc())).all()
    return [
        {
            "activity_id": row.activity_id,
            "telegram_message_id": row.telegram_message_id,
            "created_at": row.created_at.isoformat() + "Z",
        }
        for row in rows
    ]


@router.get("/events")
def events(
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_jwt_user),
) -> list[dict]:
    rows = db.scalars(select(EventLog).order_by(EventLog.created_at.desc()).limit(limit)).all()
    return [
        {
            "id": row.id,
            "event_type": row.event_type,
            "status": row.status,
            "message": row.message,
            "payload": json.loads(row.payload) if row.payload else None,
            "correlation_id": row.correlation_id,
            "created_at": row.created_at.isoformat() + "Z",
        }
        for row in rows
    ]


@router.post("/retry/{activity_id}")
def retry_activity(
    activity_id: int,
    background_tasks: BackgroundTasks,
    owner_id: int | None = None,
    _: User = Depends(require_jwt_user),
) -> dict:
    if activity_id < 1:
        raise HTTPException(status_code=400, detail="Invalid activity ID")
    background_tasks.add_task(process_activity, activity_id, owner_id, 0)
    return {"status": "queued", "activity_id": activity_id}


FEED_TYPES = {"Run", "VirtualRun", "TrailRun", "TreadmillRun", "TrackRun", "WeightTraining", "Workout"}
RUN_SPORT_TYPES = {"Run", "VirtualRun", "TrailRun", "TreadmillRun", "TrackRun"}
GYM_SPORT_TYPES = {"WeightTraining", "Workout"}


@router.get("/activities")
def activities(
    per_page: int = Query(default=15, le=50),
    page: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(require_jwt_user),
) -> list[dict]:
    if not user.access_token:
        raise HTTPException(status_code=404, detail="No user connected")
    strava = StravaService()
    raw = strava.get_athlete_activities(db, user, per_page=per_page, page=page)
    return [
        {
            "id": a["id"],
            "name": a.get("name"),
            "type": a.get("type") or a.get("sport_type"),
            "sport_type": a.get("sport_type"),
            "distance": a.get("distance"),
            "moving_time": a.get("moving_time"),
            "total_elevation_gain": a.get("total_elevation_gain"),
            "average_heartrate": a.get("average_heartrate"),
            "start_date": a.get("start_date"),
            "start_date_local": a.get("start_date_local"),
        }
        for a in raw
        if (a.get("type") or a.get("sport_type")) in FEED_TYPES
    ]


@router.get("/stored-activities")
def stored_activities(
    page: int = Query(default=1, ge=1),
    perPage: int = Query(default=15, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(require_jwt_user),
) -> dict:
    return list_activities(
        db,
        user,
        after=None,
        before=None,
        sport=None,
        type_group_name=None,
        min_distance_m=None,
        max_distance_m=None,
        min_moving_time_sec=None,
        max_moving_time_sec=None,
        has_heartrate=None,
        gear_id=None,
        trainer=None,
        page=page,
        per_page=perPage,
        sort="start_date_desc",
    )


@router.get("/activity-type-summary")
def activity_type_summary(
    db: Session = Depends(get_db),
    user: User = Depends(require_jwt_user),
) -> dict:
    this_week_start = monday_on_or_before(local_today())
    last_week_start = this_week_start - timedelta(days=7)
    rows = stat_activities_between(db, user, last_week_start, this_week_start + timedelta(days=6))

    def week(start: date) -> dict:
        end = start + timedelta(days=6)
        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "bySportType": by_sport_type([row for row in rows if start <= row.local_date <= end]),
        }

    return {"thisWeek": week(this_week_start), "lastWeek": week(last_week_start)}


@router.get("/shoe-vault")
def shoe_vault(
    db: Session = Depends(get_db),
    user: User = Depends(require_jwt_user),
) -> list[dict]:
    if not user.access_token:
        raise HTTPException(status_code=404, detail="No user connected")
    strava = StravaService()
    gears = list_gear(db)
    if not gears:
        strava.sync_gear_cache(db, user)
        gears = list_gear(db)
    result = []
    for gear in gears:
        detail = strava.get_gear_detail(db, user, gear.strava_gear_id)
        if not include_gear_in_shoe_vault(detail):
            continue
        result.append(
            {
                "strava_gear_id": gear.strava_gear_id,
                "name": gear.name,
                "is_default": gear.is_default,
                "total_distance_m": detail.get("distance", 0),
                "brand_name": detail.get("brand_name"),
                "model_name": detail.get("model_name"),
            }
        )
    return result


@router.get("/weekly-summary")
def weekly_summary(
    db: Session = Depends(get_db),
    user: User = Depends(require_jwt_user),
) -> dict:
    if not user.access_token:
        raise HTTPException(status_code=404, detail="No user connected")
    today = date.today()
    monday_this = today - timedelta(days=today.weekday())
    monday_last = monday_this - timedelta(weeks=1)
    after_epoch = int((monday_last - date(1970, 1, 1)).total_seconds())
    strava = StravaService()
    activities = strava.get_activities_since(db, user, after_epoch, max_pages=2)
    runs = [a for a in activities if (a.get("sport_type") or a.get("type")) in RUN_SPORT_TYPES]

    def empty_day() -> dict:
        return {"km": 0.0, "moving_time_s": 0, "elevation_m": 0.0, "count": 0, "activities": []}

    def empty_week() -> dict:
        return {"total_km": 0.0, "run_count": 0, "elevation_m": 0.0, "days": [empty_day() for _ in range(7)]}

    this_week = empty_week()
    last_week = empty_week()

    for a in runs:
        raw_date = (a.get("start_date_local") or a.get("start_date") or "")[:10]
        if not raw_date:
            continue
        try:
            act_date = date.fromisoformat(raw_date)
        except ValueError:
            continue
        km = (a.get("distance") or 0) / 1000
        elev = a.get("total_elevation_gain") or 0
        moving_time = a.get("moving_time") or 0
        if act_date >= monday_this:
            bucket = this_week
        elif act_date >= monday_last:
            bucket = last_week
        else:
            continue
        bucket["total_km"] += km
        bucket["run_count"] += 1
        bucket["elevation_m"] += elev
        day = bucket["days"][act_date.weekday()]
        day["km"] += km
        day["moving_time_s"] += moving_time
        day["elevation_m"] += elev
        day["count"] += 1
        day["activities"].append({
            "name": a.get("name") or "Run",
            "km": round(km, 2),
            "moving_time_s": moving_time,
            "elevation_m": round(elev),
        })

    this_week["total_km"] = round(this_week["total_km"], 2)
    last_week["total_km"] = round(last_week["total_km"], 2)
    this_week["elevation_m"] = round(this_week["elevation_m"])
    last_week["elevation_m"] = round(last_week["elevation_m"])
    for week in [this_week, last_week]:
        for day in week["days"]:
            day["km"] = round(day["km"], 2)
            day["elevation_m"] = round(day["elevation_m"])

    return {"this_week": this_week, "last_week": last_week}


@router.get("/streak")
def streak(
    db: Session = Depends(get_db),
    user: User = Depends(require_jwt_user),
) -> dict:
    if not user.access_token:
        raise HTTPException(status_code=404, detail="No user connected")
    today = date.today()
    after_epoch = int((today - timedelta(days=90) - date(1970, 1, 1)).total_seconds())
    strava = StravaService()
    activities = strava.get_activities_since(db, user, after_epoch, max_pages=5)
    runs = [
        a for a in activities
        if (a.get("sport_type") or a.get("type")) in RUN_SPORT_TYPES
        and (a.get("distance") or 0) >= 1000
    ]

    run_days: set[date] = set()
    for a in runs:
        raw = (a.get("start_date_local") or a.get("start_date") or "")[:10]
        try:
            run_days.add(date.fromisoformat(raw))
        except ValueError:
            pass

    def streak_from(start: date) -> int:
        count = 0
        d = start
        while d in run_days:
            count += 1
            d -= timedelta(days=1)
        return count

    # Current streak: start from today or yesterday
    if today in run_days:
        current_streak = streak_from(today)
    else:
        current_streak = streak_from(today - timedelta(days=1))

    best_streak = max((streak_from(d) for d in run_days), default=0)

    # PRs
    fastest_pace_entry = None
    longest_run_entry = None
    most_elevation_entry = None

    for a in runs:
        dist = a.get("distance") or 0
        moving_time = a.get("moving_time") or 0
        elev = a.get("total_elevation_gain") or 0
        raw_date = (a.get("start_date_local") or a.get("start_date") or "")[:10]
        entry = {
            "activity_name": a.get("name"),
            "activity_date": raw_date,
            "distance_m": dist,
            "moving_time_s": moving_time,
        }
        if dist >= 1000 and moving_time > 0:
            pace_sec_per_km = moving_time / (dist / 1000)
            if fastest_pace_entry is None or pace_sec_per_km < fastest_pace_entry["value_sec_per_km"]:
                fastest_pace_entry = {**entry, "value_sec_per_km": pace_sec_per_km}
        if longest_run_entry is None or dist > longest_run_entry["distance_m"]:
            longest_run_entry = entry
        if elev > 0 and (most_elevation_entry is None or elev > most_elevation_entry["elevation_m"]):
            most_elevation_entry = {**entry, "elevation_m": elev}

    return {
        "current_streak": current_streak,
        "best_streak": best_streak,
        "prs": {
            "fastest_pace": fastest_pace_entry,
            "longest_run": longest_run_entry,
            "most_elevation": most_elevation_entry,
        },
    }


@router.get("/gym-summary")
def gym_summary(
    db: Session = Depends(get_db),
    user: User = Depends(require_jwt_user),
) -> dict:
    if not user.access_token:
        raise HTTPException(status_code=404, detail="No user connected")
    today = date.today()
    jan1 = today.replace(month=1, day=1)
    after_epoch = int((jan1 - date(1970, 1, 1)).total_seconds())
    strava = StravaService()
    activities = strava.get_activities_since(db, user, after_epoch, max_pages=10)
    gym_acts = [
        a for a in activities
        if (a.get("sport_type") or a.get("type")) in GYM_SPORT_TYPES
    ]

    monday_this = today - timedelta(days=today.weekday())
    monday_last = monday_this - timedelta(weeks=1)

    this_week = {"count": 0, "duration_s": 0}
    last_week = {"count": 0, "duration_s": 0}
    year_total = 0
    month_buckets: dict[str, dict] = {}

    for a in gym_acts:
        raw_date = (a.get("start_date_local") or a.get("start_date") or "")[:10]
        if not raw_date:
            continue
        try:
            act_date = date.fromisoformat(raw_date)
        except ValueError:
            continue
        duration = a.get("moving_time") or a.get("elapsed_time") or 0
        year_total += 1
        month_key = act_date.strftime("%b")
        month_num = act_date.month
        if month_key not in month_buckets:
            month_buckets[month_key] = {"month": month_key, "count": 0, "duration_s": 0, "_num": month_num}
        month_buckets[month_key]["count"] += 1
        month_buckets[month_key]["duration_s"] += duration
        if act_date >= monday_this:
            this_week["count"] += 1
            this_week["duration_s"] += duration
        elif act_date >= monday_last:
            last_week["count"] += 1
            last_week["duration_s"] += duration

    # Sort months chronologically, take last 3, remove internal _num
    sorted_months = sorted(month_buckets.values(), key=lambda m: m["_num"])
    last_3 = sorted_months[-3:] if len(sorted_months) >= 3 else sorted_months
    months_out = [{"month": m["month"], "count": m["count"], "duration_s": m["duration_s"]} for m in last_3]

    return {
        "this_week": this_week,
        "last_week": last_week,
        "year_total": year_total,
        "months": months_out,
    }


@router.get("/gym-calendar")
def gym_calendar(
    db: Session = Depends(get_db),
    user: User = Depends(require_jwt_user),
) -> dict:
    if not user.access_token:
        raise HTTPException(status_code=404, detail="No user connected")
    today = date.today()
    after_epoch = int((today - timedelta(days=60) - date(1970, 1, 1)).total_seconds())
    strava = StravaService()
    activities = strava.get_activities_since(db, user, after_epoch, max_pages=3)
    gym_acts = [
        a for a in activities
        if (a.get("sport_type") or a.get("type")) in GYM_SPORT_TYPES
    ]

    gym_days: set[date] = set()
    for a in gym_acts:
        raw = (a.get("start_date_local") or a.get("start_date") or "")[:10]
        try:
            gym_days.add(date.fromisoformat(raw))
        except ValueError:
            pass

    month_start = today.replace(day=1)
    month_session_count = sum(1 for d in gym_days if d.year == today.year and d.month == today.month)

    # Consecutive weeks (Mon–Sun) ending this week with ≥ 1 gym session
    monday_this = today - timedelta(days=today.weekday())
    weeks_with_gym_streak = 0
    monday = monday_this
    while True:
        sunday = monday + timedelta(days=6)
        week_days = {monday + timedelta(days=i) for i in range(7)}
        if gym_days & week_days:
            weeks_with_gym_streak += 1
            monday -= timedelta(weeks=1)
        else:
            break

    return {
        "gym_days": sorted(d.isoformat() for d in gym_days),
        "month_session_count": month_session_count,
        "weeks_with_gym_streak": weeks_with_gym_streak,
        "year": today.year,
        "month": today.month,
    }
