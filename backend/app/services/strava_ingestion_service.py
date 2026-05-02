import logging
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select

from app.db import SessionLocal
from app.models import (
    StravaActivity,
    StravaActivityBestEffort,
    StravaActivityLap,
    StravaActivityMetric,
    StravaActivitySplit,
    StravaActivityZoneBucket,
    StravaAthleteZone,
    StravaIngestionJob,
    User,
)
from app.services.strava_profile_service import sync_athlete_profile, sync_athlete_stats, sync_gear_detail
from app.services.strava_service import StravaService

log = logging.getLogger("ingestion")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _athlete_id(payload: dict[str, Any], owner_id: int | None = None) -> int | None:
    athlete = payload.get("athlete")
    if isinstance(athlete, dict):
        value = athlete.get("id")
        if value is not None:
            return int(value)
    return owner_id


def _bool(value: Any) -> bool:
    return bool(value) if value is not None else False


def _cadence_spm(value: Any) -> float | None:
    return float(value) * 2 if value is not None else None


def _gap_source(value: Any) -> str:
    return "strava" if value is not None else "unavailable"


def _local_parts(value: datetime | None) -> tuple[date | None, int | None, int | None, int | None]:
    if value is None:
        return None, None, None, None
    return value.date(), value.year, value.month, value.isocalendar().week


def _seconds_per_km(distance_m: float | None, seconds: int | None) -> float | None:
    if not distance_m or distance_m <= 0 or seconds is None:
        return None
    return seconds / (distance_m / 1000)


def _mps_to_seconds_per_km(value: float | None) -> float | None:
    if not value or value <= 0:
        return None
    return 1000 / value


def _mps_to_kmh(value: float | None) -> float | None:
    return value * 3.6 if value is not None else None


def _load_user(db, owner_id: int | None) -> User | None:
    if owner_id is not None:
        user = db.scalar(select(User).where(User.strava_athlete_id == owner_id).limit(1))
        if user:
            return user
    return db.scalar(select(User).limit(1))


def _data_quality(
    detail: dict[str, Any],
    laps: list[dict[str, Any]],
    zones: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    splits_metric = detail.get("splits_metric") or []
    splits_standard = detail.get("splits_standard") or []
    zone_bucket_count = sum(len(zone.get("distribution_buckets") or []) for zone in zones or [])
    return {
        "has_activity_zones": bool(zones),
        "has_athlete_zones_snapshot": False,
        "has_laps": bool(laps),
        "has_splits": bool(splits_metric or splits_standard),
        "has_best_efforts": bool(detail.get("best_efforts") or []),
        "has_gap": detail.get("average_grade_adjusted_speed") is not None,
        "gap_source": _gap_source(detail.get("average_grade_adjusted_speed")),
        "split_sources": [
            source
            for source, values in (("metric", splits_metric), ("standard", splits_standard))
            if values
        ],
        "zone_bucket_count": zone_bucket_count,
    }


def _upsert_activity(
    db,
    detail: dict[str, Any],
    owner_id: int | None,
    laps: list[dict[str, Any]],
    zones: list[dict[str, Any]] | None,
) -> StravaActivity:
    now = _now()
    activity_id = int(detail["id"])
    existing = db.get(StravaActivity, activity_id)
    start_date_local = _parse_dt(detail.get("start_date_local"))
    local_date, local_year, local_month, local_week = _local_parts(start_date_local)
    average_gap = detail.get("average_grade_adjusted_speed")
    data_quality = _data_quality(detail, laps, zones)
    activity = existing or StravaActivity(activity_id=activity_id, first_ingested_at=now)

    activity.athlete_id = int(_athlete_id(detail, owner_id) or 0)
    activity.name = detail.get("name")
    activity.description = detail.get("description")
    activity.activity_type = detail.get("type")
    activity.sport_type = detail.get("sport_type")
    activity.workout_type = detail.get("workout_type")
    activity.start_date = _parse_dt(detail.get("start_date"))
    activity.start_date_local = start_date_local
    activity.timezone = detail.get("timezone")
    activity.local_date = local_date
    activity.local_year = local_year
    activity.local_month = local_month
    activity.local_week = local_week
    activity.distance_m = detail.get("distance")
    activity.moving_time_seconds = detail.get("moving_time")
    activity.elapsed_time_seconds = detail.get("elapsed_time")
    activity.total_elevation_gain_m = detail.get("total_elevation_gain")
    activity.elev_high_m = detail.get("elev_high")
    activity.elev_low_m = detail.get("elev_low")
    activity.average_speed_mps = detail.get("average_speed")
    activity.max_speed_mps = detail.get("max_speed")
    activity.average_grade_adjusted_speed_mps = average_gap
    activity.gap_source = _gap_source(average_gap)
    activity.has_heartrate = _bool(detail.get("has_heartrate") or detail.get("average_heartrate"))
    activity.average_heartrate_bpm = detail.get("average_heartrate")
    activity.max_heartrate_bpm = detail.get("max_heartrate")
    activity.average_cadence_spm = _cadence_spm(detail.get("average_cadence"))
    activity.average_watts = detail.get("average_watts")
    activity.max_watts = detail.get("max_watts")
    activity.weighted_average_watts = detail.get("weighted_average_watts")
    activity.kilojoules = detail.get("kilojoules")
    activity.device_watts = detail.get("device_watts")
    activity.calories = detail.get("calories")
    activity.suffer_score = detail.get("suffer_score")
    activity.trainer = detail.get("trainer")
    activity.commute = detail.get("commute")
    activity.manual = detail.get("manual")
    activity.private = detail.get("private")
    activity.flagged = detail.get("flagged")
    activity.hide_from_home = detail.get("hide_from_home")
    activity.gear_id = detail.get("gear_id")
    activity.device_name = detail.get("device_name")
    activity.has_laps = data_quality["has_laps"]
    activity.has_splits = data_quality["has_splits"]
    activity.has_best_efforts = data_quality["has_best_efforts"]
    activity.has_zones = data_quality["has_activity_zones"]
    activity.has_gap = average_gap is not None
    activity.data_quality = data_quality
    activity.detail_data = detail
    activity.source_updated_at = _parse_dt(detail.get("updated_at"))
    activity.last_ingested_at = now
    activity.deleted_at = None

    db.add(activity)
    return activity


def _replace_child_rows(
    db,
    activity_id: int,
    athlete_id: int | None,
    detail: dict[str, Any],
    laps: list[dict[str, Any]],
    zones: list[dict[str, Any]] | None,
) -> None:
    db.execute(delete(StravaActivityMetric).where(StravaActivityMetric.activity_id == activity_id))
    db.execute(delete(StravaActivityLap).where(StravaActivityLap.activity_id == activity_id))
    db.execute(delete(StravaActivitySplit).where(StravaActivitySplit.activity_id == activity_id))
    db.execute(delete(StravaActivityBestEffort).where(StravaActivityBestEffort.activity_id == activity_id))
    db.execute(delete(StravaActivityZoneBucket).where(StravaActivityZoneBucket.activity_id == activity_id))

    now = _now()
    for index, lap in enumerate(laps):
        average_gap = lap.get("average_grade_adjusted_speed")
        db.add(StravaActivityLap(
            lap_id=lap.get("id"),
            activity_id=activity_id,
            athlete_id=_athlete_id(lap, athlete_id),
            lap_index=index,
            name=lap.get("name"),
            split=lap.get("split"),
            start_date=_parse_dt(lap.get("start_date")),
            start_date_local=_parse_dt(lap.get("start_date_local")),
            distance_m=lap.get("distance"),
            moving_time_seconds=lap.get("moving_time"),
            elapsed_time_seconds=lap.get("elapsed_time"),
            average_speed_mps=lap.get("average_speed"),
            max_speed_mps=lap.get("max_speed"),
            average_grade_adjusted_speed_mps=average_gap,
            gap_source=_gap_source(average_gap),
            average_heartrate_bpm=lap.get("average_heartrate"),
            max_heartrate_bpm=lap.get("max_heartrate"),
            average_cadence_spm=_cadence_spm(lap.get("average_cadence")),
            average_watts=lap.get("average_watts"),
            device_watts=lap.get("device_watts"),
            total_elevation_gain_m=lap.get("total_elevation_gain"),
            pace_zone=lap.get("pace_zone"),
            start_index=lap.get("start_index"),
            end_index=lap.get("end_index"),
            raw_data=lap,
            created_at=now,
            updated_at=now,
        ))

    for source, rows in (("metric", detail.get("splits_metric") or []), ("standard", detail.get("splits_standard") or [])):
        for split in rows:
            average_gap = split.get("average_grade_adjusted_speed")
            db.add(StravaActivitySplit(
                activity_id=activity_id,
                split_source=source,
                split=split.get("split") or 0,
                distance_m=split.get("distance"),
                moving_time_seconds=split.get("moving_time"),
                elapsed_time_seconds=split.get("elapsed_time"),
                average_speed_mps=split.get("average_speed"),
                average_grade_adjusted_speed_mps=average_gap,
                gap_source=_gap_source(average_gap),
                average_heartrate_bpm=split.get("average_heartrate"),
                elevation_difference_m=split.get("elevation_difference"),
                pace_zone=split.get("pace_zone"),
                raw_data=split,
                created_at=now,
                updated_at=now,
            ))

    for effort in detail.get("best_efforts") or []:
        db.add(StravaActivityBestEffort(
            best_effort_id=effort.get("id"),
            activity_id=activity_id,
            name=effort.get("name"),
            distance_m=effort.get("distance"),
            moving_time_seconds=effort.get("moving_time"),
            elapsed_time_seconds=effort.get("elapsed_time"),
            start_date=_parse_dt(effort.get("start_date")),
            start_date_local=_parse_dt(effort.get("start_date_local")),
            start_index=effort.get("start_index"),
            end_index=effort.get("end_index"),
            pr_rank=effort.get("pr_rank"),
            raw_data=effort,
            created_at=now,
            updated_at=now,
        ))

    for zone in zones or []:
        zone_type = str(zone.get("type") or "unknown")
        for index, bucket in enumerate(zone.get("distribution_buckets") or []):
            db.add(StravaActivityZoneBucket(
                activity_id=activity_id,
                athlete_id=athlete_id,
                zone_type=zone_type,
                bucket_index=index + 1,
                min_value=bucket.get("min"),
                max_value=bucket.get("max"),
                time_seconds=bucket.get("time"),
                sensor_based=zone.get("sensor_based"),
                custom_zones=zone.get("custom_zones"),
                score=zone.get("score"),
                source="strava",
                raw_data=bucket,
                created_at=now,
                updated_at=now,
            ))


def _store_athlete_zones(db, athlete_id: int, athlete_zones: dict[str, Any] | None) -> bool:
    if not athlete_zones:
        return False

    now = _now()
    db.execute(delete(StravaAthleteZone).where(StravaAthleteZone.athlete_id == athlete_id))
    created = False
    for zone_type, zone_info in athlete_zones.items():
        if not isinstance(zone_info, dict):
            continue
        for index, bucket in enumerate(zone_info.get("zones") or []):
            db.add(StravaAthleteZone(
                athlete_id=athlete_id,
                zone_type=zone_type,
                bucket_index=index + 1,
                min_value=bucket.get("min"),
                max_value=bucket.get("max"),
                custom_zones=zone_info.get("custom_zones"),
                source="strava",
                effective_at=now,
                fetched_at=now,
                raw_data=bucket,
                created_at=now,
                updated_at=now,
            ))
            created = True
    return created


def _zone_seconds(db, activity_id: int) -> list[int]:
    rows = db.scalars(
        select(StravaActivityZoneBucket)
        .where(StravaActivityZoneBucket.activity_id == activity_id)
        .where(StravaActivityZoneBucket.zone_type == "heartrate")
        .order_by(StravaActivityZoneBucket.bucket_index)
        .limit(5)
    ).all()
    values = [row.time_seconds or 0 for row in rows]
    return (values + [0, 0, 0, 0, 0])[:5]


def _build_activity_metrics(db, activity: StravaActivity) -> None:
    activity_id = activity.activity_id
    zone_seconds = _zone_seconds(db, activity_id)
    metric = StravaActivityMetric(
        activity_id=activity_id,
        distance_km=(activity.distance_m / 1000) if activity.distance_m is not None else None,
        moving_time_seconds=activity.moving_time_seconds,
        elapsed_time_seconds=activity.elapsed_time_seconds,
        pace_seconds_per_km=_seconds_per_km(activity.distance_m, activity.moving_time_seconds),
        gap_seconds_per_km=_mps_to_seconds_per_km(activity.average_grade_adjusted_speed_mps),
        average_speed_kmh=_mps_to_kmh(activity.average_speed_mps),
        average_grade_adjusted_speed_kmh=_mps_to_kmh(activity.average_grade_adjusted_speed_mps),
        average_cadence_spm=activity.average_cadence_spm,
        hr_zone_1_seconds=zone_seconds[0],
        hr_zone_2_seconds=zone_seconds[1],
        hr_zone_3_seconds=zone_seconds[2],
        hr_zone_4_seconds=zone_seconds[3],
        hr_zone_5_seconds=zone_seconds[4],
        total_hr_zone_seconds=sum(zone_seconds),
        easy_seconds=zone_seconds[0] + zone_seconds[1],
        moderate_seconds=zone_seconds[2],
        hard_seconds=zone_seconds[3] + zone_seconds[4],
        lap_count=db.scalar(select(func.count(StravaActivityLap.id)).where(StravaActivityLap.activity_id == activity_id)) or 0,
        split_count=db.scalar(select(func.count(StravaActivitySplit.id)).where(StravaActivitySplit.activity_id == activity_id)) or 0,
        best_effort_count=db.scalar(select(func.count(StravaActivityBestEffort.id)).where(StravaActivityBestEffort.activity_id == activity_id)) or 0,
        fastest_split_pace_seconds_per_km=None,
        fastest_split_gap_seconds_per_km=None,
        created_at=_now(),
        updated_at=_now(),
    )

    splits = db.scalars(
        select(StravaActivitySplit).where(StravaActivitySplit.activity_id == activity_id)
    ).all()
    paces = [
        _seconds_per_km(split.distance_m, split.moving_time_seconds)
        for split in splits
    ]
    gap_paces = [
        _mps_to_seconds_per_km(split.average_grade_adjusted_speed_mps)
        for split in splits
    ]
    metric.fastest_split_pace_seconds_per_km = min((value for value in paces if value), default=None)
    metric.fastest_split_gap_seconds_per_km = min((value for value in gap_paces if value), default=None)
    db.add(metric)


def ingest_activity_event(
    activity_id: int,
    owner_id: int | None = None,
    aspect_type: str | None = "create",
    trigger_type: str = "webhook",
    job_id: int | None = None,
    backfill_run_id: int | None = None,
) -> dict[str, Any]:
    strava = StravaService()
    with SessionLocal() as db:
        job = db.get(StravaIngestionJob, job_id) if job_id else None
        if job is None:
            job = StravaIngestionJob(
                activity_id=activity_id,
                athlete_id=owner_id,
                trigger_type=trigger_type,
                aspect_type=aspect_type,
                status="queued",
                backfill_run_id=backfill_run_id,
            )
            db.add(job)
            db.commit()
            db.refresh(job)

        job.status = "running"
        job.attempt_count += 1
        job.started_at = _now()
        job.updated_at = _now()
        db.commit()

        try:
            if aspect_type == "delete":
                activity = db.get(StravaActivity, activity_id)
                if activity:
                    activity.deleted_at = _now()
                    activity.last_ingested_at = _now()
                job.status = "deleted"
                job.completed_at = _now()
                job.updated_at = _now()
                db.commit()
                return {"status": "deleted", "activity_id": activity_id}

            user = _load_user(db, owner_id)
            if not user or not user.access_token:
                raise RuntimeError("No connected Strava user found for ingestion")

            detail = strava.get_activity_detail(db, activity_id=activity_id, user=user)
            laps = detail.get("laps") or []
            if not laps:
                try:
                    laps = strava.get_activity_laps(db, activity_id=activity_id, user=user)
                except Exception as exc:
                    log.info("Lap fallback unavailable | activity=%s error=%s", activity_id, exc)
                    laps = []

            try:
                zones = strava.get_activity_zones(db, activity_id=activity_id, user=user)
            except Exception as exc:
                log.info("Zone enrichment unavailable | activity=%s error=%s", activity_id, exc)
                zones = None

            try:
                athlete_zones = strava.get_athlete_zones(db, user=user)
            except Exception as exc:
                log.info("Athlete zone snapshot unavailable | activity=%s error=%s", activity_id, exc)
                athlete_zones = None

            activity = _upsert_activity(db, detail, owner_id, laps, zones)
            db.flush()
            has_athlete_zones = _store_athlete_zones(db, activity.athlete_id, athlete_zones)
            if has_athlete_zones:
                activity.data_quality = {**activity.data_quality, "has_athlete_zones_snapshot": True}
            _replace_child_rows(db, activity_id, activity.athlete_id, detail, laps, zones)
            db.flush()
            _build_activity_metrics(db, activity)

            try:
                sync_athlete_profile(db, user, strava)
            except Exception as exc:
                log.warning("Athlete profile sync failed | activity=%s error=%s", activity_id, exc)

            try:
                sync_athlete_stats(db, user, strava)
            except Exception as exc:
                log.warning("Athlete stats sync failed | activity=%s error=%s", activity_id, exc)

            gear_id = detail.get("gear_id")
            if gear_id:
                try:
                    sync_gear_detail(db, user, gear_id, strava)
                except Exception as exc:
                    log.warning("Gear detail sync failed | activity=%s gear_id=%s error=%s", activity_id, gear_id, exc)

            job.athlete_id = activity.athlete_id
            job.status = "succeeded"
            job.last_error = None
            job.completed_at = _now()
            job.updated_at = _now()
            db.commit()
            return {"status": "succeeded", "activity_id": activity_id}
        except Exception as exc:
            db.rollback()
            job = db.get(StravaIngestionJob, job.id)
            if job:
                job.status = "failed"
                job.last_error = str(exc)
                job.completed_at = _now()
                job.updated_at = _now()
                db.commit()
            log.error("Strava ingestion failed | activity=%s error=%s", activity_id, exc, exc_info=True)
            return {"status": "failed", "activity_id": activity_id, "error": str(exc)}
