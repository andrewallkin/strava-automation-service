from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import StravaActivity, StravaActivityMetric, User


def parse_iso_date(value: str | None, field_name: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO date in YYYY-MM-DD format") from exc


def list_user_activities(
    db: Session,
    user: User,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    sport_type: str | None = None,
    limit: int = 20,
) -> list[StravaActivity]:
    if not user.strava_athlete_id:
        return []

    parsed_start = parse_iso_date(start_date, "start_date")
    parsed_end = parse_iso_date(end_date, "end_date")
    if parsed_start and parsed_end and parsed_end < parsed_start:
        raise ValueError("end_date must be on or after start_date")

    safe_limit = min(max(limit, 1), 50)
    stmt = select(StravaActivity).where(
        StravaActivity.athlete_id == user.strava_athlete_id,
        StravaActivity.deleted_at.is_(None),
    )
    if parsed_start:
        stmt = stmt.where(func.date(StravaActivity.start_date_local) >= parsed_start)
    if parsed_end:
        stmt = stmt.where(func.date(StravaActivity.start_date_local) <= parsed_end)
    if sport_type:
        stmt = stmt.where(StravaActivity.sport_type == sport_type)

    return list(
        db.scalars(
            stmt.order_by(StravaActivity.start_date_local.desc().nullslast()).limit(safe_limit)
        ).all()
    )


def get_user_activity(
    db: Session,
    user: User,
    activity_id: int,
) -> tuple[StravaActivity | None, StravaActivityMetric | None]:
    if not user.strava_athlete_id:
        return None, None

    activity = db.scalar(
        select(StravaActivity)
        .where(
            StravaActivity.activity_id == activity_id,
            StravaActivity.athlete_id == user.strava_athlete_id,
            StravaActivity.deleted_at.is_(None),
        )
        .limit(1)
    )
    if not activity:
        return None, None

    metrics = db.get(StravaActivityMetric, activity.activity_id)
    return activity, metrics
