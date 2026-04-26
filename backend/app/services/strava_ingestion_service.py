import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select

from app.db import SessionLocal
from app.models import (
    StravaActivity,
    StravaActivityBestEffort,
    StravaActivityLap,
    StravaActivitySegmentEffort,
    StravaActivitySplit,
    StravaActivityZone,
    StravaIngestionJob,
    User,
)
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


def _activity_map(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("map")
    return value if isinstance(value, dict) else {}


def _bool(value: Any) -> bool:
    return bool(value) if value is not None else False


def _load_user(db, owner_id: int | None) -> User | None:
    if owner_id is not None:
        user = db.scalar(select(User).where(User.strava_athlete_id == owner_id).limit(1))
        if user:
            return user
    return db.scalar(select(User).limit(1))


def _metadata(
    detail: dict[str, Any],
    laps: list[dict[str, Any]],
    zones: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    splits_metric = detail.get("splits_metric") or []
    splits_standard = detail.get("splits_standard") or []
    segments = detail.get("segment_efforts") or []
    best_efforts = detail.get("best_efforts") or []
    return {
        "has_laps": bool(laps),
        "has_splits": bool(splits_metric or splits_standard),
        "has_segments": bool(segments),
        "has_best_efforts": bool(best_efforts),
        "has_zones": bool(zones),
        "has_streams": False,
        "stream_fetch_deferred": True,
        "split_sources": [
            source
            for source, values in (("metric", splits_metric), ("standard", splits_standard))
            if values
        ],
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
    metadata = _metadata(detail, laps, zones)
    map_data = _activity_map(detail)
    activity = existing or StravaActivity(activity_id=activity_id, first_ingested_at=now)

    activity.athlete_id = int(_athlete_id(detail, owner_id) or 0)
    activity.name = detail.get("name")
    activity.description = detail.get("description")
    activity.activity_type = detail.get("type")
    activity.sport_type = detail.get("sport_type")
    activity.start_date = _parse_dt(detail.get("start_date"))
    activity.start_date_local = _parse_dt(detail.get("start_date_local"))
    activity.timezone = detail.get("timezone")
    activity.distance = detail.get("distance")
    activity.moving_time = detail.get("moving_time")
    activity.elapsed_time = detail.get("elapsed_time")
    activity.total_elevation_gain = detail.get("total_elevation_gain")
    activity.elev_high = detail.get("elev_high")
    activity.elev_low = detail.get("elev_low")
    activity.average_speed = detail.get("average_speed")
    activity.max_speed = detail.get("max_speed")
    activity.has_heartrate = _bool(detail.get("has_heartrate") or detail.get("average_heartrate"))
    activity.average_heartrate = detail.get("average_heartrate")
    activity.max_heartrate = detail.get("max_heartrate")
    activity.average_cadence = detail.get("average_cadence")
    activity.average_watts = detail.get("average_watts")
    activity.max_watts = detail.get("max_watts")
    activity.weighted_average_watts = detail.get("weighted_average_watts")
    activity.kilojoules = detail.get("kilojoules")
    activity.device_watts = detail.get("device_watts")
    activity.calories = detail.get("calories")
    activity.suffer_score = detail.get("suffer_score")
    activity.gear_id = detail.get("gear_id")
    activity.trainer = detail.get("trainer")
    activity.commute = detail.get("commute")
    activity.manual = detail.get("manual")
    activity.private = detail.get("private")
    activity.flagged = detail.get("flagged")
    activity.hide_from_home = detail.get("hide_from_home")
    activity.workout_type = detail.get("workout_type")
    activity.achievement_count = detail.get("achievement_count")
    activity.pr_count = detail.get("pr_count")
    activity.kudos_count = detail.get("kudos_count")
    activity.athlete_count = detail.get("athlete_count")
    activity.device_name = detail.get("device_name")
    activity.map_id = map_data.get("id")
    activity.summary_polyline = map_data.get("summary_polyline")
    activity.start_latlng = detail.get("start_latlng")
    activity.end_latlng = detail.get("end_latlng")
    activity.has_laps = metadata["has_laps"]
    activity.has_splits = metadata["has_splits"]
    activity.has_segments = metadata["has_segments"]
    activity.has_best_efforts = metadata["has_best_efforts"]
    activity.has_zones = metadata["has_zones"]
    activity.has_streams = False
    activity.detail_data = detail
    activity.ingestion_metadata = metadata
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
    db.execute(delete(StravaActivityLap).where(StravaActivityLap.activity_id == activity_id))
    db.execute(delete(StravaActivitySegmentEffort).where(StravaActivitySegmentEffort.activity_id == activity_id))
    db.execute(delete(StravaActivitySplit).where(StravaActivitySplit.activity_id == activity_id))
    db.execute(delete(StravaActivityBestEffort).where(StravaActivityBestEffort.activity_id == activity_id))
    db.execute(delete(StravaActivityZone).where(StravaActivityZone.activity_id == activity_id))

    now = _now()
    for index, lap in enumerate(laps):
        lap_athlete = _athlete_id(lap, athlete_id)
        db.add(StravaActivityLap(
            lap_id=lap.get("id"),
            activity_id=activity_id,
            athlete_id=lap_athlete,
            lap_index=index,
            name=lap.get("name"),
            split=lap.get("split"),
            start_date=_parse_dt(lap.get("start_date")),
            start_date_local=_parse_dt(lap.get("start_date_local")),
            distance=lap.get("distance"),
            moving_time=lap.get("moving_time"),
            elapsed_time=lap.get("elapsed_time"),
            average_speed=lap.get("average_speed"),
            max_speed=lap.get("max_speed"),
            average_heartrate=lap.get("average_heartrate"),
            max_heartrate=lap.get("max_heartrate"),
            average_cadence=lap.get("average_cadence"),
            average_watts=lap.get("average_watts"),
            device_watts=lap.get("device_watts"),
            total_elevation_gain=lap.get("total_elevation_gain"),
            pace_zone=lap.get("pace_zone"),
            start_index=lap.get("start_index"),
            end_index=lap.get("end_index"),
            raw_data=lap,
            created_at=now,
            updated_at=now,
        ))

    for effort in detail.get("segment_efforts") or []:
        segment = effort.get("segment") if isinstance(effort.get("segment"), dict) else {}
        db.add(StravaActivitySegmentEffort(
            segment_effort_id=effort.get("id"),
            activity_id=activity_id,
            name=effort.get("name"),
            segment_id=segment.get("id"),
            segment_name=segment.get("name"),
            start_date=_parse_dt(effort.get("start_date")),
            start_date_local=_parse_dt(effort.get("start_date_local")),
            distance=effort.get("distance"),
            moving_time=effort.get("moving_time"),
            elapsed_time=effort.get("elapsed_time"),
            start_index=effort.get("start_index"),
            end_index=effort.get("end_index"),
            average_heartrate=effort.get("average_heartrate"),
            max_heartrate=effort.get("max_heartrate"),
            average_cadence=effort.get("average_cadence"),
            average_watts=effort.get("average_watts"),
            device_watts=effort.get("device_watts"),
            is_kom=effort.get("is_kom"),
            kom_rank=effort.get("kom_rank"),
            pr_rank=effort.get("pr_rank"),
            hidden=effort.get("hidden"),
            raw_data=effort,
            created_at=now,
            updated_at=now,
        ))

    for source, rows in (("metric", detail.get("splits_metric") or []), ("standard", detail.get("splits_standard") or [])):
        for split in rows:
            db.add(StravaActivitySplit(
                activity_id=activity_id,
                split_source=source,
                split=split.get("split") or 0,
                distance=split.get("distance"),
                moving_time=split.get("moving_time"),
                elapsed_time=split.get("elapsed_time"),
                average_speed=split.get("average_speed"),
                elevation_difference=split.get("elevation_difference"),
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
            distance=effort.get("distance"),
            moving_time=effort.get("moving_time"),
            elapsed_time=effort.get("elapsed_time"),
            start_date=_parse_dt(effort.get("start_date")),
            start_date_local=_parse_dt(effort.get("start_date_local")),
            start_index=effort.get("start_index"),
            end_index=effort.get("end_index"),
            pr_rank=effort.get("pr_rank"),
            raw_data=effort,
            created_at=now,
            updated_at=now,
        ))

    for index, zone in enumerate(zones or []):
        zone_type = zone.get("type") or zone.get("resource_state") or f"zone_{index}"
        db.add(StravaActivityZone(
            activity_id=activity_id,
            zone_type=str(zone_type),
            source="strava",
            raw_data=zone,
            created_at=now,
            updated_at=now,
        ))


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

            activity = _upsert_activity(db, detail, owner_id, laps, zones)
            db.flush()
            _replace_child_rows(db, activity_id, activity.athlete_id, detail, laps, zones)

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
