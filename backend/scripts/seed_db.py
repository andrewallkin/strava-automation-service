#!/usr/bin/env python3
"""Insert fictional demo data for local screenshots (no Strava or Telegram calls)."""

from __future__ import annotations

import argparse
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import (
    EventLog,
    Gear,
    StravaActivity,
    StravaIngestionJob,
    User,
)

DEMO_GEAR_IDS = ("demo-shoe-cloudline", "demo-shoe-park")
DEMO_ATHLETE_ID = 9_900_001
DEMO_TELEGRAM_USER_ID = 9_100_001
DEMO_ACTIVITY_IDS = (
    9_901_001,
    9_901_002,
    9_901_003,
    9_901_004,
    9_901_005,
    9_901_006,
    9_901_007,
    9_901_008,
    9_901_009,
)


def _dt(days_ago: int, hour: int = 7) -> datetime:
    base = datetime.now(UTC).replace(hour=hour, minute=30, second=0, microsecond=0)
    return base - timedelta(days=days_ago)


def _local_date(d: datetime) -> date:
    return d.astimezone(UTC).date()


def clear_demo_data(db: Session) -> None:
    clauses = [
        User.strava_athlete_id == DEMO_ATHLETE_ID,
        User.telegram_user_id == DEMO_TELEGRAM_USER_ID,
        User.refresh_token == "demo-local-refresh-token",
    ]
    for user in db.scalars(select(User).where(or_(*clauses))).all():
        db.delete(user)
    for activity_id in DEMO_ACTIVITY_IDS:
        db.execute(delete(StravaActivity).where(StravaActivity.activity_id == activity_id))
    db.execute(delete(EventLog).where(EventLog.correlation_id == "demo-seed"))
    db.execute(delete(StravaIngestionJob).where(StravaIngestionJob.activity_id.in_(DEMO_ACTIVITY_IDS)))
    db.execute(delete(Gear).where(Gear.strava_gear_id.in_(DEMO_GEAR_IDS)))
    db.commit()


def seed_demo_data(db: Session) -> None:
    clear_demo_data(db)

    athlete_id = DEMO_ATHLETE_ID
    user = User(
        strava_athlete_id=athlete_id,
        telegram_user_id=DEMO_TELEGRAM_USER_ID,
        access_token=None,
        refresh_token="demo-local-refresh-token",
        expires_at=datetime.now(UTC) + timedelta(days=30),
        run_shoe_enabled=True,
        gym_hide_enabled=True,
        athlete_name="Alex Demo",
        athlete_profile_url=None,
    )
    db.add(user)
    db.flush()

    activities = [
        ("Morning Loop at Fictional Park", "Run", 8_200.0, 2_520, 0),
        ("Hill Repeats on Demo Ridge", "TrailRun", 6_500.0, 2_100, 1),
        ("Easy Recovery Jog", "Run", 5_000.0, 1_800, 2),
        ("Strength Session (hidden from home)", "WeightTraining", 0.0, 3_600, 3),
        ("Lakefront Long Run", "Run", 14_200.0, 4_800, 4),
        ("Canal Towpath Run", "Run", 7_400.0, 2_400, 8),
        ("Demo Track Intervals", "Run", 6_000.0, 1_680, 9),
        ("River Path Trail", "TrailRun", 9_100.0, 3_300, 10),
        ("Last Week Long Run", "Run", 16_500.0, 5_700, 11),
    ]

    for index, (name, sport, distance_m, moving_time, days_ago) in enumerate(activities):
        start = _dt(days_ago, hour=6 + (index % 4))
        local = _local_date(start)
        activity_id = DEMO_ACTIVITY_IDS[index]
        db.add(
            StravaActivity(
                activity_id=activity_id,
                athlete_id=athlete_id,
                name=name,
                description="Synthetic activity for local documentation screenshots.",
                activity_type=sport,
                sport_type=sport,
                start_date=start,
                start_date_local=start,
                timezone="UTC",
                local_date=local,
                local_year=local.year,
                local_month=local.month,
                local_week=local.isocalendar().week,
                distance_m=distance_m,
                moving_time_seconds=moving_time,
                elapsed_time_seconds=moving_time + 120,
                total_elevation_gain_m=45.0 if sport == "Run" else 120.0,
                average_speed_mps=(distance_m / moving_time) if distance_m and moving_time else None,
                average_heartrate_bpm=142.0 if sport.endswith("Run") else 118.0,
                has_heartrate=True,
                trainer=sport == "WeightTraining",
                hide_from_home=sport == "WeightTraining",
                data_quality={},
                detail_data={},
            )
        )
        db.add(
            StravaIngestionJob(
                activity_id=activity_id,
                athlete_id=athlete_id,
                trigger_type="webhook",
                aspect_type="create",
                status="succeeded",
                attempt_count=1,
                queued_at=start,
                started_at=start,
                completed_at=start + timedelta(seconds=4),
            )
        )

    db.add_all(
        [
            Gear(
                strava_gear_id="demo-shoe-cloudline",
                name="Cloudline Racers",
                is_default=True,
                brand_name="Fictional",
                model_name="Cloudline",
                distance_m=420_000,
                retired=False,
            ),
            Gear(
                strava_gear_id="demo-shoe-park",
                name="Park Trainers",
                is_default=False,
                brand_name="Fictional",
                model_name="Park",
                distance_m=180_000,
                retired=False,
            ),
        ]
    )

    now = datetime.now(UTC)
    events = [
        ("run_action", "ok", "Assigned fictional shoes for Morning Loop at Fictional Park"),
        ("gym_action", "ok", "Set hide_from_home on Strength Session (hidden from home)"),
        ("ingestion", "ok", "Ingested Lakefront Long Run into local store"),
        ("telegram", "ok", "Processed demo shoe-picker callback (synthetic)"),
    ]
    for index, (event_type, status, message) in enumerate(events):
        db.add(
            EventLog(
                event_type=event_type,
                status=status,
                message=message,
                correlation_id="demo-seed",
                created_at=now - timedelta(minutes=30 - index * 5),
            )
        )

    db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed fictional Strava automation demo data")
    parser.add_argument("--reset", action="store_true", help="Remove demo rows only")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.reset:
            clear_demo_data(db)
            print("Demo data removed.")
            return
        seed_demo_data(db)
        print("Seeded synthetic athlete Alex Demo with fictional activities, shoes, events, and ingestion rows.")
    finally:
        db.close()


if __name__ == "__main__":
    main()