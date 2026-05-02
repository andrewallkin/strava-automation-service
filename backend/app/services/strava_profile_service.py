import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import AthleteProfile, AthleteStats, Gear, User
from app.services.strava_service import StravaService

log = logging.getLogger("profile")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _totals(bucket: dict[str, Any], prefix: str) -> dict[str, Any]:
    """Extract a stats totals bucket into flat column kwargs."""
    return {
        f"{prefix}_count": bucket.get("count"),
        f"{prefix}_distance_m": bucket.get("distance"),
        f"{prefix}_moving_time_seconds": bucket.get("moving_time"),
        f"{prefix}_elapsed_time_seconds": bucket.get("elapsed_time"),
        f"{prefix}_elevation_gain_m": bucket.get("elevation_gain"),
    }


def sync_athlete_profile(db: Session, user: User, strava: StravaService | None = None) -> AthleteProfile:
    if strava is None:
        strava = StravaService()

    data: dict[str, Any] = strava.get_athlete_profile(db, user)
    athlete_id = int(data["id"])
    now = _now()

    raw = {k: v for k, v in data.items() if k != "clubs"}

    existing = db.get(AthleteProfile, athlete_id)
    profile = existing or AthleteProfile(athlete_id=athlete_id, created_at=now)

    profile.username = data.get("username")
    profile.firstname = data.get("firstname")
    profile.lastname = data.get("lastname")
    profile.bio = data.get("bio") or None
    profile.city = data.get("city") or None
    profile.state = data.get("state") or None
    profile.country = data.get("country") or None
    profile.sex = data.get("sex") or None
    profile.premium = data.get("premium")
    profile.summit = data.get("summit")
    profile.weight_kg = data.get("weight")
    profile.ftp_watts = data.get("ftp")
    profile.athlete_type = data.get("athlete_type")
    profile.measurement_preference = data.get("measurement_preference")
    profile.strava_created_at = _parse_dt(data.get("created_at"))
    profile.raw_data = raw
    profile.fetched_at = now
    profile.updated_at = now

    db.add(profile)
    log.info("Athlete profile synced | athlete_id=%s", athlete_id)
    return profile


def sync_athlete_stats(db: Session, user: User, strava: StravaService | None = None) -> AthleteStats:
    if strava is None:
        strava = StravaService()

    if not user.strava_athlete_id:
        raise RuntimeError("User has no strava_athlete_id; cannot fetch stats")

    athlete_id = int(user.strava_athlete_id)
    data: dict[str, Any] = strava.get_athlete_stats(db, user, athlete_id)
    now = _now()

    existing = db.get(AthleteStats, athlete_id)
    stats = existing or AthleteStats(athlete_id=athlete_id, created_at=now)

    stats.biggest_ride_distance_m = data.get("biggest_ride_distance")
    stats.biggest_climb_elevation_gain_m = data.get("biggest_climb_elevation_gain")

    recent_ride = data.get("recent_ride_totals") or {}
    stats.recent_ride_count = recent_ride.get("count")
    stats.recent_ride_distance_m = recent_ride.get("distance")
    stats.recent_ride_moving_time_seconds = recent_ride.get("moving_time")
    stats.recent_ride_elapsed_time_seconds = recent_ride.get("elapsed_time")
    stats.recent_ride_elevation_gain_m = recent_ride.get("elevation_gain")
    stats.recent_ride_achievement_count = recent_ride.get("achievement_count")

    recent_run = data.get("recent_run_totals") or {}
    stats.recent_run_count = recent_run.get("count")
    stats.recent_run_distance_m = recent_run.get("distance")
    stats.recent_run_moving_time_seconds = recent_run.get("moving_time")
    stats.recent_run_elapsed_time_seconds = recent_run.get("elapsed_time")
    stats.recent_run_elevation_gain_m = recent_run.get("elevation_gain")
    stats.recent_run_achievement_count = recent_run.get("achievement_count")

    recent_swim = data.get("recent_swim_totals") or {}
    stats.recent_swim_count = recent_swim.get("count")
    stats.recent_swim_distance_m = recent_swim.get("distance")
    stats.recent_swim_moving_time_seconds = recent_swim.get("moving_time")
    stats.recent_swim_elapsed_time_seconds = recent_swim.get("elapsed_time")
    stats.recent_swim_elevation_gain_m = recent_swim.get("elevation_gain")
    stats.recent_swim_achievement_count = recent_swim.get("achievement_count")

    all_ride = data.get("all_ride_totals") or {}
    stats.all_ride_count = all_ride.get("count")
    stats.all_ride_distance_m = all_ride.get("distance")
    stats.all_ride_moving_time_seconds = all_ride.get("moving_time")
    stats.all_ride_elapsed_time_seconds = all_ride.get("elapsed_time")
    stats.all_ride_elevation_gain_m = all_ride.get("elevation_gain")

    all_run = data.get("all_run_totals") or {}
    stats.all_run_count = all_run.get("count")
    stats.all_run_distance_m = all_run.get("distance")
    stats.all_run_moving_time_seconds = all_run.get("moving_time")
    stats.all_run_elapsed_time_seconds = all_run.get("elapsed_time")
    stats.all_run_elevation_gain_m = all_run.get("elevation_gain")

    all_swim = data.get("all_swim_totals") or {}
    stats.all_swim_count = all_swim.get("count")
    stats.all_swim_distance_m = all_swim.get("distance")
    stats.all_swim_moving_time_seconds = all_swim.get("moving_time")
    stats.all_swim_elapsed_time_seconds = all_swim.get("elapsed_time")
    stats.all_swim_elevation_gain_m = all_swim.get("elevation_gain")

    ytd_ride = data.get("ytd_ride_totals") or {}
    stats.ytd_ride_count = ytd_ride.get("count")
    stats.ytd_ride_distance_m = ytd_ride.get("distance")
    stats.ytd_ride_moving_time_seconds = ytd_ride.get("moving_time")
    stats.ytd_ride_elapsed_time_seconds = ytd_ride.get("elapsed_time")
    stats.ytd_ride_elevation_gain_m = ytd_ride.get("elevation_gain")

    ytd_run = data.get("ytd_run_totals") or {}
    stats.ytd_run_count = ytd_run.get("count")
    stats.ytd_run_distance_m = ytd_run.get("distance")
    stats.ytd_run_moving_time_seconds = ytd_run.get("moving_time")
    stats.ytd_run_elapsed_time_seconds = ytd_run.get("elapsed_time")
    stats.ytd_run_elevation_gain_m = ytd_run.get("elevation_gain")

    ytd_swim = data.get("ytd_swim_totals") or {}
    stats.ytd_swim_count = ytd_swim.get("count")
    stats.ytd_swim_distance_m = ytd_swim.get("distance")
    stats.ytd_swim_moving_time_seconds = ytd_swim.get("moving_time")
    stats.ytd_swim_elapsed_time_seconds = ytd_swim.get("elapsed_time")
    stats.ytd_swim_elevation_gain_m = ytd_swim.get("elevation_gain")

    stats.raw_data = data
    stats.fetched_at = now
    stats.updated_at = now

    db.add(stats)
    log.info("Athlete stats synced | athlete_id=%s", athlete_id)
    return stats


def sync_gear_detail(db: Session, user: User, gear_id: str, strava: StravaService | None = None) -> Gear:
    if strava is None:
        strava = StravaService()

    data: dict[str, Any] = strava.get_gear_detail(db, user, gear_id)
    now = _now()

    from sqlalchemy import select
    existing = db.scalar(select(Gear).where(Gear.strava_gear_id == gear_id))
    gear = existing or Gear(strava_gear_id=gear_id)

    if not existing:
        gear.name = data.get("name") or gear_id
        gear.is_default = bool(data.get("primary"))

    gear.nickname = data.get("nickname") or None
    gear.distance_m = data.get("distance")
    gear.brand_name = data.get("brand_name") or None
    gear.model_name = data.get("model_name") or None
    gear.description = data.get("description") or None
    gear.retired = data.get("retired")
    gear.notification_distance_m = data.get("notification_distance")
    gear.raw_data = data
    gear.fetched_at = now

    db.add(gear)
    log.info("Gear detail synced | gear_id=%s", gear_id)
    return gear
