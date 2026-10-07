from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.external_errors import ExternalAPIError
from app.mcp.formatting import is_run_sport
from app.mcp.queries import get_activity_best_efforts, get_activity_laps, get_gear_names, require_user_activity
from app.models import (
    AthleteProfile,
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
from app.services.external_stats import STRENGTH_SPORTS, StatActivity, type_group


def _pace(distance_m: float | None, moving_time: int | None, stored: float | None) -> int | None:
    if stored and stored > 0:
        return round(stored)
    if not distance_m or distance_m <= 0 or moving_time is None:
        return None
    return round(moving_time / (distance_m / 1000))


def _latlng(value: object) -> list[float] | None:
    if not isinstance(value, list) or len(value) != 2:
        return None
    try:
        return [float(value[0]), float(value[1])]
    except (TypeError, ValueError):
        return None


def _detail(activity: StravaActivity) -> dict:
    raw = activity.detail_data if isinstance(activity.detail_data, dict) else {}
    return raw


def activity_summary(activity: StravaActivity, metrics: StravaActivityMetric | None = None) -> dict:
    detail = _detail(activity)
    polyline = None
    map_value = detail.get("map")
    if isinstance(map_value, dict):
        polyline = map_value.get("summary_polyline")
    temp = detail.get("average_temp")
    external_id = detail.get("external_id")
    return {
        "id": str(activity.activity_id),
        "name": activity.name,
        "sportType": activity.sport_type,
        "typeGroup": type_group(activity.sport_type),
        "startDate": activity.start_date.isoformat() if activity.start_date else None,
        "startDateLocal": activity.start_date_local.isoformat() if activity.start_date_local else None,
        "timezone": activity.timezone,
        "elapsedTimeSec": activity.elapsed_time_seconds,
        "movingTimeSec": activity.moving_time_seconds,
        "distanceM": activity.distance_m,
        "elevationGainM": activity.total_elevation_gain_m,
        "averageSpeedMps": activity.average_speed_mps,
        "maxSpeedMps": activity.max_speed_mps,
        "averagePaceSecPerKm": _pace(
            activity.distance_m,
            activity.moving_time_seconds,
            metrics.pace_seconds_per_km if metrics else None,
        ),
        "averageHeartrate": activity.average_heartrate_bpm,
        "maxHeartrate": activity.max_heartrate_bpm,
        "averageCadenceSpm": activity.average_cadence_spm,
        "calories": activity.calories,
        "sufferScore": activity.suffer_score,
        "trainer": activity.trainer,
        "commute": activity.commute,
        "manual": activity.manual,
        "deviceName": activity.device_name,
        "gearId": activity.gear_id,
        "description": activity.description,
        "externalId": external_id if external_id else None,
        "averageTempC": temp if isinstance(temp, (int, float)) else None,
        "startLatlng": _latlng(detail.get("start_latlng")),
        "endLatlng": _latlng(detail.get("end_latlng")),
        "hasMapPolyline": bool(polyline),
        "perceivedExertion": detail.get("perceived_exertion"),
        "gradeAdjustedSpeedMps": activity.average_grade_adjusted_speed_mps,
    }


def lap_payload(lap: StravaActivityLap) -> dict:
    return {
        "lapIndex": lap.lap_index,
        "name": lap.name,
        "startDate": lap.start_date.isoformat() if lap.start_date else None,
        "startIndex": lap.start_index,
        "endIndex": lap.end_index,
        "elapsedTimeSec": lap.elapsed_time_seconds,
        "movingTimeSec": lap.moving_time_seconds,
        "distanceM": lap.distance_m,
        "elevationGainM": lap.total_elevation_gain_m,
        "averageSpeedMps": lap.average_speed_mps,
        "maxSpeedMps": lap.max_speed_mps,
        "averageHeartrate": lap.average_heartrate_bpm,
        "maxHeartrate": lap.max_heartrate_bpm,
        "averageCadenceSpm": lap.average_cadence_spm,
        "averageWatts": lap.average_watts,
    }


def split_payload(split: StravaActivitySplit) -> dict:
    pace = None
    if split.distance_m and split.distance_m > 0 and split.moving_time_seconds is not None:
        pace = round(split.moving_time_seconds / (split.distance_m / 1000))
    return {
        "split": split.split,
        "distanceM": split.distance_m,
        "elapsedTimeSec": split.elapsed_time_seconds,
        "movingTimeSec": split.moving_time_seconds,
        "elevationDifferenceM": split.elevation_difference_m,
        "averageSpeedMps": split.average_speed_mps,
        "averageHeartrate": split.average_heartrate_bpm,
        "averagePaceSecPerKm": pace,
        "paceZone": split.pace_zone,
    }


def zone_payload(bucket: StravaActivityZoneBucket) -> dict:
    return {
        "zone": bucket.bucket_index,
        "min": bucket.min_value,
        "max": bucket.max_value,
        "seconds": bucket.time_seconds,
    }


def best_effort_payload(effort: StravaActivityBestEffort) -> dict:
    return {
        "name": effort.name,
        "distanceM": effort.distance_m,
        "movingTimeSec": effort.moving_time_seconds,
        "elapsedTimeSec": effort.elapsed_time_seconds,
        "startIndex": effort.start_index,
        "endIndex": effort.end_index,
        "prRank": effort.pr_rank,
        "startDate": effort.start_date.isoformat() if effort.start_date else None,
    }


def segment_efforts(activity: StravaActivity) -> list[dict]:
    raw = _detail(activity).get("segment_efforts")
    if not isinstance(raw, list):
        return []
    items = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        segment = entry.get("segment") if isinstance(entry.get("segment"), dict) else {}
        items.append(
            {
                "name": entry.get("name") or segment.get("name"),
                "distanceM": entry.get("distance") if entry.get("distance") is not None else segment.get("distance"),
                "elapsedTimeSec": entry.get("elapsed_time"),
                "segmentId": segment.get("id"),
            }
        )
    return items


def require_activity(db: Session, user: User, activity_id: int) -> StravaActivity:
    activity = require_user_activity(db, user, activity_id)
    if activity is None:
        raise ExternalAPIError(404, "not_found", "Activity not found")
    return activity


def _metrics_by_id(db: Session, activity_ids: list[int]) -> dict[int, StravaActivityMetric]:
    if not activity_ids:
        return {}
    rows = db.scalars(select(StravaActivityMetric).where(StravaActivityMetric.activity_id.in_(activity_ids))).all()
    return {row.activity_id: row for row in rows}


def _apply_type_group(stmt, group: str | None):
    if not group:
        return stmt
    if group == "run":
        return stmt.where(
            StravaActivity.sport_type.in_(("Run", "TrailRun", "TreadmillRun", "VirtualRun"))
            | StravaActivity.sport_type.ilike("%Run%")
        )
    if group == "strength":
        return stmt.where(StravaActivity.sport_type.in_(tuple(STRENGTH_SPORTS)))
    return stmt.where(
        StravaActivity.sport_type.is_(None)
        | (
            ~StravaActivity.sport_type.in_(("Run", "TrailRun", "TreadmillRun", "VirtualRun", *STRENGTH_SPORTS))
            & ~StravaActivity.sport_type.ilike("%Run%")
        )
    )


def list_activities(
    db: Session,
    user: User,
    *,
    after: date | None,
    before: date | None,
    sport: str | None,
    type_group_name: str | None,
    min_distance_m: float | None,
    max_distance_m: float | None,
    min_moving_time_sec: int | None,
    max_moving_time_sec: int | None,
    has_heartrate: bool | None,
    gear_id: str | None,
    trainer: bool | None,
    page: int,
    per_page: int,
    sort: str,
) -> dict:
    if not user.strava_athlete_id:
        return {"data": [], "pagination": _pagination(page, per_page, 0)}
    stmt = select(StravaActivity).where(
        StravaActivity.athlete_id == user.strava_athlete_id,
        StravaActivity.deleted_at.is_(None),
    )
    if after:
        stmt = stmt.where(func.date(StravaActivity.start_date_local) >= after)
    if before:
        stmt = stmt.where(func.date(StravaActivity.start_date_local) <= before)
    if sport:
        stmt = stmt.where(StravaActivity.sport_type == sport)
    stmt = _apply_type_group(stmt, type_group_name)
    if min_distance_m is not None:
        stmt = stmt.where(StravaActivity.distance_m >= min_distance_m)
    if max_distance_m is not None:
        stmt = stmt.where(StravaActivity.distance_m <= max_distance_m)
    if min_moving_time_sec is not None:
        stmt = stmt.where(StravaActivity.moving_time_seconds >= min_moving_time_sec)
    if max_moving_time_sec is not None:
        stmt = stmt.where(StravaActivity.moving_time_seconds <= max_moving_time_sec)
    if has_heartrate is not None:
        stmt = stmt.where(StravaActivity.has_heartrate.is_(has_heartrate))
    if gear_id:
        stmt = stmt.where(StravaActivity.gear_id == gear_id)
    if trainer is not None:
        stmt = stmt.where(StravaActivity.trainer.is_(trainer))
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    order = StravaActivity.start_date_local.asc() if sort == "start_date_asc" else StravaActivity.start_date_local.desc()
    rows = list(db.scalars(stmt.order_by(order.nullslast()).offset((page - 1) * per_page).limit(per_page)).all())
    metrics = _metrics_by_id(db, [row.activity_id for row in rows])
    return {
        "data": [activity_summary(row, metrics.get(row.activity_id)) for row in rows],
        "pagination": _pagination(page, per_page, total),
    }


def _pagination(page: int, per_page: int, total: int) -> dict:
    total_pages = (total + per_page - 1) // per_page if per_page else 0
    return {
        "page": page,
        "perPage": per_page,
        "total": total,
        "totalPages": total_pages,
        "nextPage": page + 1 if page < total_pages else None,
    }


def activity_detail(db: Session, user: User, activity_id: int) -> dict:
    activity = require_activity(db, user, activity_id)
    metrics = db.get(StravaActivityMetric, activity.activity_id)
    payload = activity_summary(activity, metrics)
    names = get_gear_names(db)
    payload["gearName"] = names.get(activity.gear_id) if activity.gear_id else None
    payload["laps"] = [lap_payload(lap) for lap in get_activity_laps(db, activity.activity_id)]
    splits = db.scalars(
        select(StravaActivitySplit)
        .where(StravaActivitySplit.activity_id == activity.activity_id)
        .order_by(StravaActivitySplit.split_source, StravaActivitySplit.split)
    ).all()
    payload["splits"] = {
        "metric": [split_payload(row) for row in splits if row.split_source == "metric"],
        "standard": [split_payload(row) for row in splits if row.split_source == "standard"],
    }
    buckets = db.scalars(
        select(StravaActivityZoneBucket)
        .where(StravaActivityZoneBucket.activity_id == activity.activity_id)
        .order_by(StravaActivityZoneBucket.zone_type, StravaActivityZoneBucket.bucket_index)
    ).all()
    payload["zones"] = {
        "heartRate": [zone_payload(row) for row in buckets if row.zone_type == "heartrate"],
        "pace": [zone_payload(row) for row in buckets if row.zone_type == "pace"],
        "power": [zone_payload(row) for row in buckets if row.zone_type == "power"],
    }
    payload["bestEfforts"] = [best_effort_payload(row) for row in get_activity_best_efforts(db, activity.activity_id)]
    payload["sameDayActivities"] = _same_day(db, user, activity)
    payload["segmentEfforts"] = segment_efforts(activity)
    return payload


def _same_day(db: Session, user: User, activity: StravaActivity) -> list[dict]:
    if activity.local_date is None or not user.strava_athlete_id:
        return []
    rows = db.scalars(
        select(StravaActivity)
        .where(
            StravaActivity.athlete_id == user.strava_athlete_id,
            StravaActivity.local_date == activity.local_date,
            StravaActivity.activity_id != activity.activity_id,
            StravaActivity.deleted_at.is_(None),
        )
        .order_by(StravaActivity.start_date_local.asc().nullslast())
    ).all()
    return [
        {
            "id": str(row.activity_id),
            "name": row.name,
            "sportType": row.sport_type,
            "typeGroup": type_group(row.sport_type),
            "startDateLocal": row.start_date_local.isoformat() if row.start_date_local else None,
        }
        for row in rows
    ]


def laps_payload(db: Session, user: User, activity_id: int) -> dict:
    activity = require_activity(db, user, activity_id)
    return {"activityId": str(activity.activity_id), "laps": [lap_payload(lap) for lap in get_activity_laps(db, activity.activity_id)]}


def splits_payload(db: Session, user: User, activity_id: int) -> dict:
    activity = require_activity(db, user, activity_id)
    detail = activity_detail(db, user, activity_id)
    return {"activityId": str(activity.activity_id), "metric": detail["splits"]["metric"], "standard": detail["splits"]["standard"]}


def zones_payload(db: Session, user: User, activity_id: int) -> dict:
    activity = require_activity(db, user, activity_id)
    detail = activity_detail(db, user, activity_id)
    zones = detail["zones"]
    return {"activityId": str(activity.activity_id), **zones}


def best_efforts_payload(db: Session, user: User, activity_id: int) -> dict:
    activity = require_activity(db, user, activity_id)
    return {
        "activityId": str(activity.activity_id),
        "bestEfforts": [best_effort_payload(row) for row in get_activity_best_efforts(db, activity.activity_id)],
    }


def athlete_payload(db: Session, user: User) -> dict:
    profile = None
    if user.strava_athlete_id:
        profile = db.get(AthleteProfile, user.strava_athlete_id)
    zones = []
    if user.strava_athlete_id:
        zones = list(
            db.scalars(
                select(StravaAthleteZone)
                .where(StravaAthleteZone.athlete_id == user.strava_athlete_id)
                .order_by(StravaAthleteZone.zone_type, StravaAthleteZone.effective_at.desc(), StravaAthleteZone.bucket_index)
            ).all()
        )
    latest: dict[str, datetime] = {}
    for zone in zones:
        current = latest.get(zone.zone_type)
        if current is None or zone.effective_at > current:
            latest[zone.zone_type] = zone.effective_at
    def zone_list(zone_type: str) -> list[dict]:
        effective = latest.get(zone_type)
        if effective is None:
            return []
        return [
            {"zone": zone.bucket_index, "min": zone.min_value, "max": zone.max_value}
            for zone in zones
            if zone.zone_type == zone_type and zone.effective_at == effective
        ]
    gear_rows = list(db.scalars(select(Gear).order_by(Gear.name)).all())
    name = None
    if profile and (profile.firstname or profile.lastname):
        name = " ".join(part for part in (profile.firstname, profile.lastname) if part)
    elif user.athlete_name:
        name = user.athlete_name
    return {
        "id": str(user.strava_athlete_id) if user.strava_athlete_id else None,
        "name": name,
        "measurementPreference": profile.measurement_preference if profile else None,
        "weightKg": profile.weight_kg if profile else None,
        "ftpWatts": profile.ftp_watts if profile else None,
        "heartRateZones": zone_list("heart_rate"),
        "powerZones": zone_list("power"),
        "gear": [
            {
                "id": row.strava_gear_id,
                "name": row.name,
                "brand": row.brand_name,
                "model": row.model_name,
                "distanceM": row.distance_m,
                "retired": row.retired,
            }
            for row in gear_rows
        ],
    }


def health_payload(db: Session, user: User) -> dict:
    if not user.strava_athlete_id:
        return {
            "ok": True,
            "lastIngestedAt": None,
            "activityCount": 0,
            "oldestActivityAt": None,
            "newestActivityAt": None,
        }
    scope = select(StravaActivity).where(
        StravaActivity.athlete_id == user.strava_athlete_id,
        StravaActivity.deleted_at.is_(None),
    )
    count = db.scalar(select(func.count()).select_from(scope.subquery())) or 0
    oldest = db.scalar(select(func.min(StravaActivity.start_date)).where(
        StravaActivity.athlete_id == user.strava_athlete_id,
        StravaActivity.deleted_at.is_(None),
    ))
    newest = db.scalar(select(func.max(StravaActivity.start_date)).where(
        StravaActivity.athlete_id == user.strava_athlete_id,
        StravaActivity.deleted_at.is_(None),
    ))
    last = db.scalar(select(func.max(StravaActivity.last_ingested_at)).where(
        StravaActivity.athlete_id == user.strava_athlete_id,
        StravaActivity.deleted_at.is_(None),
    ))
    return {
        "ok": True,
        "lastIngestedAt": last.isoformat() if last else None,
        "activityCount": count,
        "oldestActivityAt": oldest.isoformat() if oldest else None,
        "newestActivityAt": newest.isoformat() if newest else None,
    }


def stat_activities_between(db: Session, user: User, start: date, end: date) -> list[StatActivity]:
    if not user.strava_athlete_id:
        return []
    rows = db.scalars(
        select(StravaActivity).where(
            StravaActivity.athlete_id == user.strava_athlete_id,
            StravaActivity.deleted_at.is_(None),
            StravaActivity.local_date.is_not(None),
            StravaActivity.local_date >= start,
            StravaActivity.local_date <= end,
        )
    ).all()
    metrics = _metrics_by_id(db, [row.activity_id for row in rows])
    items = []
    for row in rows:
        if row.local_date is None or row.start_date_local is None:
            continue
        metric = metrics.get(row.activity_id)
        zones = (0, 0, 0, 0, 0)
        if metric is not None:
            zones = (
                metric.hr_zone_1_seconds,
                metric.hr_zone_2_seconds,
                metric.hr_zone_3_seconds,
                metric.hr_zone_4_seconds,
                metric.hr_zone_5_seconds,
            )
        items.append(
            StatActivity(
                activity_id=row.activity_id,
                sport_type=row.sport_type,
                local_date=row.local_date,
                start_local=row.start_date_local,
                distance_m=row.distance_m,
                moving_time_seconds=row.moving_time_seconds,
                elevation_gain_m=row.total_elevation_gain_m,
                average_cadence_spm=row.average_cadence_spm,
                has_heartrate=bool(row.has_heartrate),
                hr_zones=zones,
                description=row.description,
                elapsed_time_seconds=row.elapsed_time_seconds,
            )
        )
    return items


def assert_run_filter_matches(sport_type: str | None, group: str) -> bool:
    """Used by tests to keep SQL grouping aligned with type_group()."""
    return type_group(sport_type) == group or (group == "run" and is_run_sport(sport_type))
