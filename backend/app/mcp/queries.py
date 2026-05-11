from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timedelta

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    AthleteProfile,
    AthleteStats,
    Gear,
    StravaActivity,
    StravaActivityBestEffort,
    StravaActivityLap,
    StravaActivityMetric,
    StravaActivitySplit,
    StravaActivityZoneBucket,
    StravaAthleteZone,
    User,
)
from app.mcp.formatting import RUN_SPORT_TYPES


SKIPPED_MCP_TOOLS: dict[str, str] = {}

SPORT_TYPE_ALIASES = {
    "run": "Run",
    "running": "Run",
    "trailrun": "TrailRun",
    "trail_run": "TrailRun",
    "trail run": "TrailRun",
    "treadmillrun": "TreadmillRun",
    "treadmill_run": "TreadmillRun",
    "treadmill run": "TreadmillRun",
    "virtualrun": "VirtualRun",
    "virtual_run": "VirtualRun",
    "virtual run": "VirtualRun",
}


def parse_iso_date(value: str | None, field_name: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO date in YYYY-MM-DD format") from exc


def today() -> date:
    return date.today()


def parse_activity_date(value: str, field_name: str = "date") -> date:
    lowered = value.lower().strip()
    if lowered == "today":
        return today()
    if lowered == "yesterday":
        return today() - timedelta(days=1)
    parsed = parse_iso_date(value, field_name)
    if parsed is None:
        raise ValueError(f"{field_name} is required")
    return parsed


def validate_date_range(start_date: str | None, end_date: str | None) -> tuple[date | None, date | None]:
    parsed_start = parse_iso_date(start_date, "start_date")
    parsed_end = parse_iso_date(end_date, "end_date")
    if parsed_start and parsed_end and parsed_end < parsed_start:
        raise ValueError("end_date must be on or after start_date")
    return parsed_start, parsed_end


def bounded_limit(limit: int, default: int = 25, maximum: int = 100) -> int:
    value = limit if limit is not None else default
    return min(max(int(value), 1), maximum)


def normalize_sport_types(sport_type: str | Sequence[str] | None, *, default_runs: bool = False) -> list[str]:
    if not sport_type:
        return list(RUN_SPORT_TYPES) if default_runs else []

    def canonicalize(value: str) -> str:
        stripped = value.strip()
        return SPORT_TYPE_ALIASES.get(stripped.lower(), stripped)

    if isinstance(sport_type, str):
        return [canonicalize(part) for part in sport_type.split(",") if part.strip()]
    return [canonicalize(part) for part in sport_type if part]


def activity_scope(user: User) -> Select[tuple[StravaActivity]]:
    stmt = select(StravaActivity).where(StravaActivity.deleted_at.is_(None))
    if not user.strava_athlete_id:
        return stmt.where(StravaActivity.athlete_id == -1)
    return stmt.where(StravaActivity.athlete_id == user.strava_athlete_id)


def apply_activity_filters(
    stmt: Select[tuple[StravaActivity]],
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    sport_types: Sequence[str] | None = None,
    min_distance_km: float | None = None,
    max_distance_km: float | None = None,
    min_duration_min: float | None = None,
    max_duration_min: float | None = None,
    workout_type: int | None = None,
    gear_id: str | None = None,
    has_heartrate: bool | None = None,
    has_laps: bool | None = None,
    trainer: bool | None = None,
) -> Select[tuple[StravaActivity]]:
    if start_date:
        stmt = stmt.where(func.date(StravaActivity.start_date_local) >= start_date)
    if end_date:
        stmt = stmt.where(func.date(StravaActivity.start_date_local) <= end_date)
    if sport_types:
        stmt = stmt.where(StravaActivity.sport_type.in_(sport_types))
    if min_distance_km is not None:
        stmt = stmt.where(StravaActivity.distance_m >= min_distance_km * 1000)
    if max_distance_km is not None:
        stmt = stmt.where(StravaActivity.distance_m <= max_distance_km * 1000)
    if min_duration_min is not None:
        stmt = stmt.where(StravaActivity.moving_time_seconds >= min_duration_min * 60)
    if max_duration_min is not None:
        stmt = stmt.where(StravaActivity.moving_time_seconds <= max_duration_min * 60)
    if workout_type is not None:
        stmt = stmt.where(StravaActivity.workout_type == workout_type)
    if gear_id:
        stmt = stmt.where(StravaActivity.gear_id == gear_id)
    if has_heartrate is not None:
        stmt = stmt.where(StravaActivity.has_heartrate.is_(has_heartrate))
    if has_laps is not None:
        stmt = stmt.where(StravaActivity.has_laps.is_(has_laps))
    if trainer is not None:
        stmt = stmt.where(StravaActivity.trainer.is_(trainer))
    return stmt


def search_user_activities(
    db: Session,
    user: User,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    sport_type: str | Sequence[str] | None = None,
    min_distance_km: float | None = None,
    max_distance_km: float | None = None,
    min_duration_min: float | None = None,
    max_duration_min: float | None = None,
    workout_type: int | None = None,
    gear_id: str | None = None,
    has_heartrate: bool | None = None,
    has_laps: bool | None = None,
    trainer: bool | None = None,
    limit: int = 25,
    default_runs: bool = True,
) -> tuple[list[StravaActivity], int]:
    parsed_start, parsed_end = validate_date_range(start_date, end_date)
    sport_types = normalize_sport_types(sport_type, default_runs=default_runs)
    stmt = apply_activity_filters(
        activity_scope(user),
        start_date=parsed_start,
        end_date=parsed_end,
        sport_types=sport_types,
        min_distance_km=min_distance_km,
        max_distance_km=max_distance_km,
        min_duration_min=min_duration_min,
        max_duration_min=max_duration_min,
        workout_type=workout_type,
        gear_id=gear_id,
        has_heartrate=has_heartrate,
        has_laps=has_laps,
        trainer=trainer,
    )
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = list(
        db.scalars(
            stmt.order_by(StravaActivity.start_date_local.desc().nullslast()).limit(bounded_limit(limit))
        ).all()
    )
    return rows, total


def list_user_activities(
    db: Session,
    user: User,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    sport_type: str | None = None,
    limit: int = 20,
) -> list[StravaActivity]:
    rows, _ = search_user_activities(
        db,
        user,
        start_date=start_date,
        end_date=end_date,
        sport_type=sport_type,
        limit=min(limit, 50),
        default_runs=False,
    )
    return rows


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


def require_user_activity(db: Session, user: User, activity_id: int) -> StravaActivity | None:
    activity, _ = get_user_activity(db, user, activity_id)
    return activity


def get_activity_metrics(db: Session, activity_id: int) -> StravaActivityMetric | None:
    return db.get(StravaActivityMetric, activity_id)


def get_activity_laps(db: Session, activity_id: int) -> list[StravaActivityLap]:
    return list(
        db.scalars(
            select(StravaActivityLap)
            .where(StravaActivityLap.activity_id == activity_id)
            .order_by(StravaActivityLap.lap_index)
        ).all()
    )


def get_activity_splits(db: Session, activity_id: int, unit: str = "metric") -> list[StravaActivitySplit]:
    source = "standard" if unit == "standard" else "metric"
    return list(
        db.scalars(
            select(StravaActivitySplit)
            .where(
                StravaActivitySplit.activity_id == activity_id,
                StravaActivitySplit.split_source == source,
            )
            .order_by(StravaActivitySplit.split)
        ).all()
    )


def get_activity_best_efforts(db: Session, activity_id: int) -> list[StravaActivityBestEffort]:
    return list(
        db.scalars(
            select(StravaActivityBestEffort)
            .where(StravaActivityBestEffort.activity_id == activity_id)
            .order_by(StravaActivityBestEffort.distance_m.asc().nullslast())
        ).all()
    )


def get_activity_zone_buckets(
    db: Session,
    activity_id: int,
    zone_type: str = "heartrate",
) -> list[StravaActivityZoneBucket]:
    return list(
        db.scalars(
            select(StravaActivityZoneBucket)
            .where(
                StravaActivityZoneBucket.activity_id == activity_id,
                StravaActivityZoneBucket.zone_type == zone_type,
            )
            .order_by(StravaActivityZoneBucket.bucket_index)
        ).all()
    )


def get_latest_athlete_zones(
    db: Session,
    user: User,
    zone_type: str = "heart_rate",
) -> list[StravaAthleteZone]:
    if not user.strava_athlete_id:
        return []
    latest_effective = db.scalar(
        select(func.max(StravaAthleteZone.effective_at)).where(
            StravaAthleteZone.athlete_id == user.strava_athlete_id,
            StravaAthleteZone.zone_type == zone_type,
        )
    )
    if latest_effective is None:
        return []
    return list(
        db.scalars(
            select(StravaAthleteZone)
            .where(
                StravaAthleteZone.athlete_id == user.strava_athlete_id,
                StravaAthleteZone.zone_type == zone_type,
                StravaAthleteZone.effective_at == latest_effective,
            )
            .order_by(StravaAthleteZone.bucket_index)
        ).all()
    )


def get_gear_names(db: Session) -> dict[str, str]:
    rows = db.scalars(select(Gear)).all()
    return {row.strava_gear_id: row.name for row in rows}


def get_athlete_profile(db: Session, user: User) -> AthleteProfile | None:
    if not user.strava_athlete_id:
        return None
    return db.get(AthleteProfile, user.strava_athlete_id)


def get_athlete_stats(db: Session, user: User) -> AthleteStats | None:
    if not user.strava_athlete_id:
        return None
    return db.get(AthleteStats, user.strava_athlete_id)


def list_gear_details(db: Session, *, include_retired: bool = False) -> list[Gear]:
    stmt = select(Gear)
    if not include_retired:
        stmt = stmt.where(or_(Gear.retired.is_(False), Gear.retired.is_(None)))
    return list(db.scalars(stmt.order_by(Gear.distance_m.desc().nullslast(), Gear.name.asc())).all())


def list_runs_between(
    db: Session,
    user: User,
    *,
    start: date | None = None,
    end: date | None = None,
    sport_types: Sequence[str] | None = RUN_SPORT_TYPES,
) -> list[StravaActivity]:
    stmt = apply_activity_filters(activity_scope(user), start_date=start, end_date=end, sport_types=sport_types)
    return list(db.scalars(stmt.order_by(StravaActivity.start_date_local.asc().nullslast())).all())


def find_user_activity_by_date(
    db: Session,
    user: User,
    date_value: str,
    *,
    sport_type: str | Sequence[str] | None = None,
) -> list[StravaActivity]:
    parsed = parse_activity_date(date_value)
    sport_types = normalize_sport_types(sport_type, default_runs=True)
    stmt = apply_activity_filters(activity_scope(user), start_date=parsed, end_date=parsed, sport_types=sport_types)
    return list(db.scalars(stmt.order_by(StravaActivity.start_date_local.asc().nullslast())).all())


def find_similar_user_runs(
    db: Session,
    user: User,
    reference_activity_id: int,
    *,
    lookback_days: int = 90,
    distance_tolerance_pct: float = 15,
    elev_tolerance_pct: float = 25,
    elev_tolerance_abs_m: float = 50,
    limit: int = 10,
) -> tuple[StravaActivity | None, list[tuple[StravaActivity, float]]]:
    reference = require_user_activity(db, user, reference_activity_id)
    if not reference or not reference.start_date_local or not reference.distance_m:
        return reference, []
    start = reference.start_date_local.date() - timedelta(days=min(max(lookback_days, 1), 365))
    end = reference.start_date_local.date()
    stmt = apply_activity_filters(
        activity_scope(user),
        start_date=start,
        end_date=end,
        sport_types=[reference.sport_type] if reference.sport_type else list(RUN_SPORT_TYPES),
    ).where(StravaActivity.activity_id != reference_activity_id)
    if reference.trainer is not None:
        stmt = stmt.where(StravaActivity.trainer.is_(reference.trainer))
    rows = list(db.scalars(stmt).all())
    scored: list[tuple[StravaActivity, float]] = []
    ref_elev = reference.total_elevation_gain_m or 0
    for row in rows:
        if not row.distance_m:
            continue
        distance_delta_pct = abs(row.distance_m - reference.distance_m) / reference.distance_m * 100
        if distance_delta_pct > distance_tolerance_pct:
            continue
        elev_delta = abs((row.total_elevation_gain_m or 0) - ref_elev)
        elev_allowed = max(elev_tolerance_abs_m, ref_elev * elev_tolerance_pct / 100)
        if elev_delta > elev_allowed:
            continue
        elev_delta_pct = (elev_delta / ref_elev * 100) if ref_elev else 0
        scored.append((row, distance_delta_pct + 0.5 * elev_delta_pct))
    scored.sort(
        key=lambda item: (
            item[1],
            item[0].start_date_local.timestamp() if isinstance(item[0].start_date_local, datetime) else 0,
        )
    )
    return reference, scored[:bounded_limit(limit, maximum=25)]


def activities_with_best_effort(
    db: Session,
    user: User,
    *,
    effort_name: str | None = None,
    lookback_days: int = 365,
    pr_only: bool = False,
    limit: int = 50,
) -> list[tuple[StravaActivity, StravaActivityBestEffort]]:
    start = today() - timedelta(days=min(max(lookback_days, 1), 3650))
    stmt = (
        select(StravaActivity, StravaActivityBestEffort)
        .join(StravaActivityBestEffort, StravaActivityBestEffort.activity_id == StravaActivity.activity_id)
        .where(
            StravaActivity.athlete_id == user.strava_athlete_id,
            StravaActivity.deleted_at.is_(None),
            func.date(StravaActivity.start_date_local) >= start,
        )
        .order_by(StravaActivity.start_date_local.desc().nullslast())
        .limit(bounded_limit(limit, maximum=200))
    )
    if effort_name:
        stmt = stmt.where(func.lower(StravaActivityBestEffort.name) == effort_name.lower())
    if pr_only:
        stmt = stmt.where(StravaActivityBestEffort.pr_rank == 1)
    return list(db.execute(stmt).all())


def count_child_rows(db: Session, activity_id: int) -> dict[str, int]:
    return {
        "laps": db.scalar(select(func.count(StravaActivityLap.id)).where(StravaActivityLap.activity_id == activity_id)) or 0,
        "splits_metric": db.scalar(
            select(func.count(StravaActivitySplit.id)).where(
                StravaActivitySplit.activity_id == activity_id,
                StravaActivitySplit.split_source == "metric",
            )
        ) or 0,
        "splits_standard": db.scalar(
            select(func.count(StravaActivitySplit.id)).where(
                StravaActivitySplit.activity_id == activity_id,
                StravaActivitySplit.split_source == "standard",
            )
        ) or 0,
        "best_efforts": db.scalar(
            select(func.count(StravaActivityBestEffort.id)).where(StravaActivityBestEffort.activity_id == activity_id)
        ) or 0,
        "zones": db.scalar(
            select(func.count(StravaActivityZoneBucket.id)).where(StravaActivityZoneBucket.activity_id == activity_id)
        ) or 0,
    }


def missing_run_dates(rows: Sequence[StravaActivity], start: date, end: date) -> list[date]:
    active_dates = {row.start_date_local.date() for row in rows if row.start_date_local}
    days = (end - start).days
    return [start + timedelta(days=offset) for offset in range(days + 1) if start + timedelta(days=offset) not in active_dates]
