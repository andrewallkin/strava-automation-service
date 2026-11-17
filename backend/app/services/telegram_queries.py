"""Local activity and gear replies for Telegram commands."""

from datetime import date, datetime, time, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Gear, StravaActivity, User
from app.services.telegram_messages import (
    RUN_TYPES,
    WeekActivity,
    format_recent_line,
    format_shoe_line,
    format_streak,
    format_week,
)


def _monday(today: date) -> date:
    return today - timedelta(days=today.weekday())


def _activities(db: Session, user: User):
    if user.strava_athlete_id is None:
        return []
    return list(
        db.scalars(
            select(StravaActivity).where(
                StravaActivity.athlete_id == user.strava_athlete_id,
                StravaActivity.deleted_at.is_(None),
            )
        ).all()
    )


def _as_week_activity(row: StravaActivity) -> WeekActivity:
    start = row.start_date_local or datetime.combine(row.local_date or date.min, time.min)
    return WeekActivity(
        name=row.name or "Activity",
        sport_type=row.sport_type or row.activity_type or "Activity",
        start=start,
        distance_m=row.distance_m or 0,
        moving_s=row.moving_time_seconds or 0,
    )


def week_text(db: Session, user: User, today: date) -> str:
    monday = _monday(today)
    previous_monday = monday - timedelta(days=7)
    sunday = monday + timedelta(days=6)
    current: list[WeekActivity] = []
    previous_m = 0.0
    for row in _activities(db, user):
        if row.local_date is None:
            continue
        if monday <= row.local_date <= sunday:
            current.append(_as_week_activity(row))
        elif previous_monday <= row.local_date < monday:
            previous_m += row.distance_m or 0
    return format_week(monday, current, previous_m / 1000)


def recent_text(db: Session, user: User) -> str:
    rows = [row for row in _activities(db, user) if row.start_date_local is not None]
    rows.sort(key=lambda row: row.start_date_local, reverse=True)
    chosen = rows[:5]
    if not chosen:
        return "No activities stored."
    return "\n".join(
        format_recent_line(
            row.sport_type or row.activity_type or "Activity",
            row.name or "Activity",
            row.distance_m or 0,
            row.moving_time_seconds or 0,
        )
        for row in chosen
    )


def streak_text(db: Session, user: User, today: date) -> str:
    run_days = {
        row.local_date
        for row in _activities(db, user)
        if row.local_date is not None
        and (row.sport_type or row.activity_type) in RUN_TYPES
        and (row.distance_m or 0) >= 1000
    }
    start = today if today in run_days else today - timedelta(days=1)
    days = 0
    cursor = start
    while cursor in run_days:
        days += 1
        cursor -= timedelta(days=1)
    return format_streak(days)


def shoes_text(db: Session) -> str:
    shoes = list(
        db.scalars(select(Gear).where(or_(Gear.retired.is_(False), Gear.retired.is_(None))).order_by(Gear.name.asc())).all()
    )
    if not shoes:
        return "No shoes stored."
    return "\n".join(
        format_shoe_line(
            shoe.nickname or shoe.name,
            shoe.distance_m or 0,
            shoe.notification_distance_m,
        )
        for shoe in shoes
    )
