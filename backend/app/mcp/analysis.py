from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from math import floor

from sqlalchemy.orm import Session

from app.mcp import queries
from app.mcp.formatting import (
    RUN_SPORT_TYPES,
    coefficient_of_variation_pct,
    format_activity_list,
    format_date,
    format_distance,
    format_duration,
    format_optional,
    format_pace,
    format_speed,
    format_table,
    format_zone_boundaries,
    is_run_sport,
    km,
    linear_slope,
    mean,
    median,
    mps_to_seconds_per_km,
    pct,
    seconds_per_km,
)
from app.models import (
    StravaActivity,
    StravaActivityLap,
    StravaActivitySplit,
    StravaActivityZoneBucket,
    User,
)


def _not_found() -> str:
    return "Activity not found for the authenticated user."


def _run_only(activity: StravaActivity) -> str | None:
    if not is_run_sport(activity.sport_type):
        return f"This tool is run-only; activity {activity.activity_id} is type {activity.sport_type or 'unknown'}."
    return None


def _pace_for_activity(activity: StravaActivity) -> float | None:
    return seconds_per_km(activity.distance_m, activity.moving_time_seconds)


def _lap_pace(lap: StravaActivityLap) -> float | None:
    return mps_to_seconds_per_km(lap.average_speed_mps) or seconds_per_km(lap.distance_m, lap.moving_time_seconds)


def _split_pace(split: StravaActivitySplit) -> float | None:
    return mps_to_seconds_per_km(split.average_speed_mps) or seconds_per_km(split.distance_m, split.moving_time_seconds)


def _zoned_seconds(buckets: list[StravaActivityZoneBucket]) -> list[int]:
    values = [bucket.time_seconds or 0 for bucket in buckets[:5]]
    return (values + [0, 0, 0, 0, 0])[:5]


def _activity_row(activity: StravaActivity, lap_count: int | None = None) -> list[object]:
    return [
        activity.activity_id,
        format_date(activity.start_date_local),
        activity.name or "Untitled",
        activity.sport_type or "unknown",
        format_distance(activity.distance_m, 3),
        format_duration(activity.moving_time_seconds),
        format_pace(_pace_for_activity(activity)),
        format_optional(activity.average_heartrate_bpm, " bpm", 0),
        format_optional(activity.total_elevation_gain_m, " m", 0),
        "" if lap_count is None else lap_count,
    ]


def search_activities_text(
    db: Session,
    user: User,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    sport_type: str | None = None,
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
) -> str:
    rows, total = queries.search_user_activities(
        db,
        user,
        start_date=start_date,
        end_date=end_date,
        sport_type=sport_type,
        min_distance_km=min_distance_km,
        max_distance_km=max_distance_km,
        min_duration_min=min_duration_min,
        max_duration_min=max_duration_min,
        workout_type=workout_type,
        gear_id=gear_id,
        has_heartrate=has_heartrate,
        has_laps=has_laps,
        trainer=trainer,
        limit=limit,
        default_runs=True,
    )
    if not rows:
        return "No activities found for that filter."
    lap_counts = {row.activity_id: queries.count_child_rows(db, row.activity_id)["laps"] for row in rows}
    table = format_table(
        ["activity_id", "date", "name", "sport", "distance", "duration", "pace", "avg_hr", "elev", "laps"],
        [_activity_row(row, lap_counts[row.activity_id]) for row in rows],
    )
    return f"Found {len(rows)} of {total} matching activities.\n{table}"


def list_recent_runs_text(db: Session, user: User, n: int = 10) -> str:
    rows, _ = queries.search_user_activities(db, user, limit=n, default_runs=True)
    return format_activity_list(rows)


def find_activity_by_date_text(
    db: Session,
    user: User,
    *,
    date_value: str,
    sport_type: str | None = None,
) -> str:
    rows = queries.find_user_activity_by_date(db, user, date_value, sport_type=sport_type)
    if not rows:
        return "No activities found on that date."
    table = format_table(
        ["activity_id", "date", "name", "sport", "distance", "duration", "start_time_local"],
        [
            [
                row.activity_id,
                format_date(row.start_date_local),
                row.name or "Untitled",
                row.sport_type or "unknown",
                format_distance(row.distance_m, 3),
                format_duration(row.moving_time_seconds),
                row.start_date_local.isoformat() if row.start_date_local else "unknown",
            ]
            for row in rows
        ],
    )
    return table


def get_heart_rate_zones_text(db: Session, user: User) -> str:
    zones = queries.get_latest_athlete_zones(db, user)
    if not zones:
        return "Athlete heart-rate zones are not cached in strava_athlete_zones."
    return format_zone_boundaries(zones)


def get_athlete_profile_text(db: Session, user: User) -> str:
    profile = queries.get_athlete_profile(db, user)
    if not profile:
        return "Athlete profile is not cached in athlete_profile."
    name = " ".join(part for part in (profile.firstname, profile.lastname) if part).strip()
    shoes = queries.list_gear_details(db, include_retired=True)
    shoe_rows = [
        [
            shoe.nickname or shoe.name,
            format_distance(shoe.distance_m, 1),
            "yes" if shoe.retired else "no",
        ]
        for shoe in shoes[:10]
    ]
    lines = [
        f"name: {name or profile.username or 'unknown'}",
        f"sex: {profile.sex or 'unknown'}",
        f"weight_kg: {format_optional(profile.weight_kg, '', 1)}",
        f"city: {profile.city or 'unknown'}",
        f"country: {profile.country or 'unknown'}",
        f"created_at: {format_date(profile.strava_created_at)}",
        f"fetched_at: {format_date(profile.fetched_at)}",
        "",
        "Shoes:",
        format_table(["nickname", "distance", "retired"], shoe_rows) if shoe_rows else "No shoes cached.",
    ]
    if profile.weight_kg is not None:
        lines.append("Notes: Strava weight can be stale; fetched_at indicates when the cache was refreshed.")
    return "\n".join(lines)


def get_shoe_mileage_text(db: Session, user: User, include_retired: bool = False) -> str:
    shoes = queries.list_gear_details(db, include_retired=include_retired)
    if not shoes:
        return "No shoes found in the gear cache."
    now = queries.today()
    last_90 = queries.list_runs_between(db, user, start=now - timedelta(days=90), end=now)
    last_30 = [row for row in last_90 if row.start_date_local and row.start_date_local.date() >= now - timedelta(days=30)]
    all_runs = queries.list_runs_between(db, user, start=None, end=now)
    rows = []
    for shoe in shoes:
        used_all = [row for row in all_runs if row.gear_id == shoe.strava_gear_id]
        used_90 = [row for row in last_90 if row.gear_id == shoe.strava_gear_id]
        used_30 = [row for row in last_30 if row.gear_id == shoe.strava_gear_id]
        last_used = max((row.start_date_local for row in used_all if row.start_date_local), default=None)
        total_km = (shoe.distance_m or 0) / 1000
        flag = ""
        if total_km >= 800:
            flag = "replace"
        elif total_km >= 600:
            flag = "consider replacement"
        rows.append(
            [
                shoe.nickname or shoe.name,
                f"{total_km:.1f}",
                format_date(last_used),
                len(used_90),
                f"{sum(row.distance_m or 0 for row in used_30) / 1000:.1f}",
                "yes" if shoe.retired else "no",
                flag,
            ]
        )
    return "\n".join(
        [
            format_table(["name", "total_km", "last_used", "runs_90d", "last_30d_km", "retired", "flag"], rows),
            "Notes: total_km comes from Strava gear detail; recent usage is computed from locally ingested runs with gear_id.",
        ]
    )


def get_athlete_stats_text(db: Session, user: User) -> str:
    stats = queries.get_athlete_stats(db, user)
    if not stats:
        return "Athlete stats are not cached in athlete_stats."

    def row(prefix: str, label: str) -> list[object]:
        return [
            label,
            getattr(stats, f"{prefix}_count") or 0,
            format_distance(getattr(stats, f"{prefix}_distance_m"), 1),
            format_duration(getattr(stats, f"{prefix}_moving_time_seconds")),
            format_optional(getattr(stats, f"{prefix}_elevation_gain_m"), " m", 0),
        ]

    rows = [
        row("recent_run", "recent runs"),
        row("ytd_run", "YTD runs"),
        row("all_run", "all runs"),
        row("recent_ride", "recent rides"),
        row("ytd_ride", "YTD rides"),
        row("all_ride", "all rides"),
        row("recent_swim", "recent swims"),
        row("ytd_swim", "YTD swims"),
        row("all_swim", "all swims"),
    ]
    return "\n".join(
        [
            format_table(["bucket", "count", "distance", "moving_time", "elev"], rows),
            f"Biggest ride distance: {format_distance(stats.biggest_ride_distance_m, 1)}",
            f"Biggest climb elevation gain: {format_optional(stats.biggest_climb_elevation_gain_m, ' m', 0)}",
            f"Fetched at: {format_date(stats.fetched_at)}",
        ]
    )


def get_activity_summary_text(db: Session, user: User, activity_id: int) -> str:
    activity, metrics = queries.get_user_activity(db, user, activity_id)
    if not activity:
        return _not_found()
    gear_names = queries.get_gear_names(db)
    counts = queries.count_child_rows(db, activity_id)
    workout_label = {1: "race", 2: "long_run", 3: "workout"}.get(activity.workout_type, "default")
    pace = metrics.pace_seconds_per_km if metrics and metrics.pace_seconds_per_km else _pace_for_activity(activity)
    lines = [
        f"Activity {activity.activity_id}: {activity.name or 'Untitled'}",
        f"- Date local: {format_date(activity.start_date_local)}",
        f"- Sport: {activity.sport_type or activity.activity_type or 'unknown'}",
        f"- Workout type: {workout_label}",
        f"- Distance: {format_distance(activity.distance_m, 3)}",
        f"- Moving time: {format_duration(activity.moving_time_seconds)}",
        f"- Elapsed time: {format_duration(activity.elapsed_time_seconds)}",
        f"- Average pace: {format_pace(pace)} ({format_speed(activity.average_speed_mps)})",
        f"- Average HR: {format_optional(activity.average_heartrate_bpm, ' bpm', 0)}",
        f"- Max HR: {format_optional(activity.max_heartrate_bpm, ' bpm', 0)}",
        f"- Average cadence: {format_optional(activity.average_cadence_spm, ' spm', 0)}",
        f"- Elevation gain: {format_optional(activity.total_elevation_gain_m, ' m', 0)}",
        f"- Calories: {format_optional(activity.calories, '', 0)}",
        f"- Suffer score: {format_optional(activity.suffer_score, '', 0)}",
        f"- Gear: {gear_names.get(activity.gear_id or '', activity.gear_id or 'none')}",
        (
            "- Available detail: "
            f"laps={counts['laps']}, splits_metric={counts['splits_metric']}, "
            f"splits_standard={counts['splits_standard']}, best_efforts={counts['best_efforts']}, "
            f"zones={counts['zones']}"
        ),
    ]
    unavailable = []
    if not activity.has_heartrate:
        unavailable.append("heart rate")
    for flag, label in (("laps", "laps"), ("splits_metric", "metric splits"), ("zones", "HR zones")):
        if counts[flag] == 0:
            unavailable.append(label)
    if unavailable:
        lines.append("Notes: unavailable detail includes " + ", ".join(unavailable) + ".")
    return "\n".join(lines)


def get_activity_full_details_text(db: Session, user: User, activity_id: int) -> str:
    activity = queries.require_user_activity(db, user, activity_id)
    if not activity:
        return _not_found()
    summary = get_activity_summary_text(db, user, activity_id)
    detail = activity.detail_data or {}
    description = activity.description or detail.get("description")
    if description and len(description) > 500:
        description = description[:500] + "... [truncated]"
    extra = [
        "",
        "Additional details:",
        f"- Description: {description or 'none'}",
        f"- Device: {activity.device_name or detail.get('device_name') or 'unknown'}",
        f"- Timezone: {activity.timezone or 'unknown'}",
        f"- Average temp: {format_optional(detail.get('average_temp'), ' C', 0)}",
        f"- Perceived exertion: {format_optional(detail.get('perceived_exertion'))}",
        f"- Achievement count: {format_optional(detail.get('achievement_count'))}",
        f"- PR count: {format_optional(detail.get('pr_count'))}",
        f"- Kudos count: {format_optional(detail.get('kudos_count'))}",
        "Notes: segment-effort rows and dedicated PR scalar columns are not in the current schema; detail_data is used where available.",
    ]
    return summary + "\n".join(extra)


def classify_workout_type_value(
    db: Session,
    user: User,
    activity: StravaActivity,
) -> tuple[str, str, list[str]]:
    laps = queries.get_activity_laps(db, activity.activity_id)
    zones = _zoned_seconds(queries.get_activity_zone_buckets(db, activity.activity_id))
    signals: list[str] = []
    if activity.trainer or activity.sport_type in ("TreadmillRun", "VirtualRun"):
        return "treadmill", "high", ["trainer or treadmill sport type"]
    if activity.workout_type == 1:
        return "race", "high", ["Strava workout_type=1"]
    interval = _detect_intervals(laps)
    signals.extend(interval["signals"])
    if interval["is_interval"]:
        return "intervals", "high", signals
    if activity.workout_type == 2:
        return "long_run", "high", ["Strava workout_type=2"]
    if activity.distance_m and activity.distance_m >= 15000:
        lookback = queries.list_runs_between(
            db,
            user,
            start=(activity.start_date_local.date() - timedelta(days=56)) if activity.start_date_local else None,
            end=activity.start_date_local.date() if activity.start_date_local else None,
        )
        max_distance = max((row.distance_m or 0 for row in lookback), default=0)
        if max_distance and activity.distance_m >= 0.6 * max_distance:
            return "long_run", "medium", [f"distance {activity.distance_m / 1000:.1f} km is long relative to recent max"]
    total_zone = sum(zones)
    if total_zone:
        easy_pct = (zones[0] + zones[1]) / total_zone * 100
        z3_pct = zones[2] / total_zone * 100
        signals.append(f"easy-zone share {easy_pct:.1f}%")
        if easy_pct >= 80 and (activity.distance_m or 0) < 8000:
            return "recovery", "medium", signals
        if easy_pct >= 80:
            return "easy_run", "medium", signals
        if z3_pct >= 25:
            return "tempo", "medium", signals + [f"Z3 share {z3_pct:.1f}%"]
    if not laps and not total_zone:
        return "unknown", "low", ["no lap or HR-zone data"]
    return "general_aerobic", "low", signals or ["fallback classification"]


def classify_workout_type_text(db: Session, user: User, activity_id: int) -> str:
    activity = queries.require_user_activity(db, user, activity_id)
    if not activity:
        return _not_found()
    result = _run_only(activity)
    if result:
        return result
    workout_type, confidence, signals = classify_workout_type_value(db, user, activity)
    return "\n".join(
        [
            f"type: {workout_type}",
            f"confidence: {confidence}",
            "signals_used:",
            *[f"  - {signal}" for signal in signals],
        ]
    )


def _detect_intervals(laps: list[StravaActivityLap]) -> dict[str, object]:
    if len(laps) < 6:
        return {"is_interval": False, "signals": ["fewer than 6 laps"]}
    distances = [lap.distance_m for lap in laps if lap.distance_m]
    speeds = [lap.average_speed_mps for lap in laps if lap.average_speed_mps]
    distance_cv = coefficient_of_variation_pct(distances) or 0
    slow = min(speeds) if speeds else 0
    fast = max(speeds) if speeds else 0
    separation = ((fast - slow) / slow * 100) if slow else 0
    threshold = median(speeds) or 0
    labels = ["W" if (lap.average_speed_mps or 0) >= threshold else "R" for lap in laps]
    transitions = sum(1 for left, right in zip(labels, labels[1:]) if left != right)
    signals = [
        f"lap_distance_cv: {distance_cv:.1f}%",
        f"pace_cluster_separation: {separation:.1f}%",
        f"alternations_detected: {transitions}",
    ]
    return {
        "is_interval": distance_cv >= 10 and separation >= 20 and transitions >= 3,
        "signals": signals,
        "labels": labels,
    }


def get_activity_laps_text(db: Session, user: User, activity_id: int) -> str:
    activity = queries.require_user_activity(db, user, activity_id)
    if not activity:
        return _not_found()
    laps = queries.get_activity_laps(db, activity_id)
    if not laps:
        return "No laps are stored for this activity."
    rows = []
    notes = []
    for lap in laps:
        if lap.distance_m is not None and lap.distance_m < 50:
            notes.append(f"lap {lap.lap_index} is an auto-end fragment under 50 m")
        rows.append(
            [
                lap.lap_index,
                lap.name or "",
                format_distance(lap.distance_m, 3),
                format_duration(lap.moving_time_seconds),
                format_pace(_lap_pace(lap)),
                format_optional(lap.average_heartrate_bpm, " bpm", 0),
                format_optional(lap.max_heartrate_bpm, " bpm", 0),
                format_optional(lap.average_cadence_spm, " spm", 0),
                format_optional(lap.total_elevation_gain_m, " m", 0),
                format_optional(lap.pace_zone),
            ]
        )
    text = format_table(["lap", "name", "distance", "time", "pace", "avg_hr", "max_hr", "cad", "elev", "pace_zone"], rows)
    if notes:
        text += "\nNotes: " + "; ".join(notes)
    return text


def analyze_intervals_text(db: Session, user: User, activity_id: int) -> str:
    activity = queries.require_user_activity(db, user, activity_id)
    if not activity:
        return _not_found()
    workout_type, _, signals = classify_workout_type_value(db, user, activity)
    if workout_type != "intervals":
        return "No interval structure detected. Use analyze_pacing for steady-state runs."
    laps = queries.get_activity_laps(db, activity_id)
    threshold = median([lap.average_speed_mps for lap in laps]) or 0
    work = [lap for lap in laps if (lap.average_speed_mps or 0) >= threshold]
    rest = [lap for lap in laps if lap not in work]
    work_paces = [_lap_pace(lap) for lap in work]
    hr_values = [lap.average_heartrate_bpm for lap in work]
    cad_values = [lap.average_cadence_spm for lap in work]
    rows = [
        [
            index,
            f"{lap.distance_m or 0:.0f} m",
            format_duration(lap.moving_time_seconds),
            format_pace(_lap_pace(lap)),
            format_optional(lap.average_heartrate_bpm, " bpm", 0),
            format_optional(lap.max_heartrate_bpm, " bpm", 0),
            format_optional(lap.average_cadence_spm, " spm", 0),
        ]
        for index, lap in enumerate(work, 1)
    ]
    recovery = []
    for work_lap in work:
        following = next((lap for lap in rest if lap.lap_index == work_lap.lap_index + 1), None)
        if following:
            recovery.append((work_lap.max_heartrate_bpm, work_lap.average_heartrate_bpm, following.average_heartrate_bpm))
    max_drop = [values[0] - values[2] for values in recovery if values[0] is not None and values[2] is not None]
    avg_drop = [values[1] - values[2] for values in recovery if values[1] is not None and values[2] is not None]
    ratio = (mean([lap.moving_time_seconds for lap in work]) or 0) / (mean([lap.moving_time_seconds for lap in rest]) or 1)
    zones = queries.get_latest_athlete_zones(db, user)
    return "\n".join(
        [
            f"Workout: {len(work)} work laps, {len(rest)} rest/other laps",
            "Detected via: " + "; ".join(signals),
            "",
            "Work reps:",
            format_table(["rep", "distance", "time", "pace", "avg_hr", "max_hr", "cad"], rows),
            "",
            f"Consistency: pace CV {format_optional(coefficient_of_variation_pct(work_paces), '%', 1)}, HR CV {format_optional(coefficient_of_variation_pct(hr_values), '%', 1)}",
            f"Recovery HR drop (work_max -> rest_avg): avg {format_optional(mean(max_drop), ' bpm', 0)}; work_avg -> rest_avg avg {format_optional(mean(avg_drop), ' bpm', 0)}",
            f"Fade: pace slope {format_optional(linear_slope(work_paces), ' sec/km per rep', 1)}, HR slope {format_optional(linear_slope(hr_values), ' bpm per rep', 1)}, cadence slope {format_optional(linear_slope(cad_values), ' spm per rep', 1)}",
            f"Work:rest ratio = 1:{(1 / ratio if ratio else 0):.2f}",
            format_zone_boundaries(zones),
        ]
    )


def compare_laps_within_activity_text(db: Session, user: User, activity_id: int) -> str:
    laps = queries.get_activity_laps(db, activity_id) if queries.require_user_activity(db, user, activity_id) else []
    if not laps:
        return "No laps are stored for this activity."
    rows = []
    previous = None
    for lap in laps:
        pace = _lap_pace(lap)
        previous_pace = _lap_pace(previous) if previous else None
        rows.append(
            [
                lap.lap_index,
                format_pace(pace),
                "" if previous_pace is None or pace is None else f"{pace - previous_pace:+.0f}s/km",
                format_optional(lap.average_heartrate_bpm, " bpm", 0),
                "" if not previous or lap.average_heartrate_bpm is None or previous.average_heartrate_bpm is None else f"{lap.average_heartrate_bpm - previous.average_heartrate_bpm:+.0f}",
                format_optional(lap.average_cadence_spm, " spm", 0),
                format_optional(lap.total_elevation_gain_m, " m", 0),
            ]
        )
        previous = lap
    return format_table(["lap", "pace", "pace_delta", "avg_hr", "hr_delta", "cad", "elev"], rows)


def get_warmup_cooldown_quality_text(db: Session, user: User, activity_id: int) -> str:
    activity = queries.require_user_activity(db, user, activity_id)
    if not activity:
        return _not_found()
    laps = queries.get_activity_laps(db, activity_id)
    if len(laps) < 3:
        return "Not enough lap data to assess warmup/cooldown quality."
    zones = queries.get_latest_athlete_zones(db, user)
    z3_floor = zones[2].min_value if len(zones) >= 3 else None
    warmup = laps[0]
    cooldown = laps[-1]
    warmup_ok = (warmup.moving_time_seconds or 0) >= 480 and (z3_floor is None or (warmup.average_heartrate_bpm or 0) < z3_floor)
    cooldown_ok = (cooldown.moving_time_seconds or 0) >= 300 and (z3_floor is None or (cooldown.average_heartrate_bpm or 0) < z3_floor)
    return "\n".join(
        [
            f"Warmup: {format_distance(warmup.distance_m, 3)} in {format_duration(warmup.moving_time_seconds)}, avg HR {format_optional(warmup.average_heartrate_bpm, ' bpm', 0)} - {'adequate' if warmup_ok else 'limited'}",
            f"Cooldown: {format_distance(cooldown.distance_m, 3)} in {format_duration(cooldown.moving_time_seconds)}, avg HR {format_optional(cooldown.average_heartrate_bpm, ' bpm', 0)} - {'adequate' if cooldown_ok else 'limited'}",
            "Notes: without streams, end-of-cooldown HR is approximated by the final lap average.",
        ]
    )


def get_activity_splits_text(db: Session, user: User, activity_id: int, unit: str = "metric") -> str:
    if not queries.require_user_activity(db, user, activity_id):
        return _not_found()
    splits = queries.get_activity_splits(db, activity_id, unit)
    if not splits:
        return f"No {unit} splits are stored for this activity."
    rows = []
    notes = []
    for split in splits:
        distance_km = km(split.distance_m, 3)
        if unit == "metric" and distance_km is not None and distance_km < 0.7:
            notes.append(f"split {split.split} is fractional")
        rows.append(
            [
                split.split,
                format_distance(split.distance_m, 3),
                format_duration(split.moving_time_seconds),
                format_pace(_split_pace(split)),
                format_pace(mps_to_seconds_per_km(split.average_grade_adjusted_speed_mps)),
                format_optional(split.average_heartrate_bpm, " bpm", 0),
                format_optional(split.elevation_difference_m, " m", 0),
                format_optional(split.pace_zone),
            ]
        )
    text = format_table(["split", "distance", "time", "pace", "gap", "avg_hr", "elev", "pace_zone"], rows)
    if notes:
        text += "\nNotes: " + "; ".join(notes)
    return text


def analyze_pacing_text(db: Session, user: User, activity_id: int, unit: str = "metric") -> str:
    activity = queries.require_user_activity(db, user, activity_id)
    if not activity:
        return _not_found()
    workout_type, _, _ = classify_workout_type_value(db, user, activity)
    if workout_type == "intervals":
        return "This was an interval workout - call analyze_intervals."
    splits = [split for split in queries.get_activity_splits(db, activity_id, unit) if (split.distance_m or 0) >= 700]
    if len(splits) < 2:
        return "Not enough complete splits to analyze pacing."
    paces = [_split_pace(split) for split in splits]
    midpoint = len(splits) // 2
    first = mean(paces[:midpoint])
    second = mean(paces[midpoint:])
    delta = (second - first) if first is not None and second is not None else None
    split_type = "even"
    if delta is not None and delta <= -5:
        split_type = "negative_split"
    elif delta is not None and delta >= 5:
        split_type = "positive_split"
    fastest = min(splits, key=lambda split: _split_pace(split) or 99999)
    slowest = max(splits, key=lambda split: _split_pace(split) or 0)
    return "\n".join(
        [
            f"Pacing: {split_type} ({format_optional(delta, ' sec/km in 2nd half', 0)})",
            f"First half avg pace: {format_pace(first)}",
            f"Second half avg pace: {format_pace(second)}",
            f"Pace CV: {format_optional(coefficient_of_variation_pct(paces), '%', 1)}",
            f"Fastest split: {fastest.split} @ {format_pace(_split_pace(fastest))}",
            f"Slowest split: {slowest.split} @ {format_pace(_split_pace(slowest))}",
            f"Fade slope: {format_optional(linear_slope(paces), ' sec/km per split', 1)}",
        ]
    )


def analyze_grade_adjusted_pace_text(db: Session, user: User, activity_id: int) -> str:
    if not queries.require_user_activity(db, user, activity_id):
        return _not_found()
    splits = queries.get_activity_splits(db, activity_id, "metric")
    rows = []
    deltas = []
    gaps = []
    for split in splits:
        pace = _split_pace(split)
        gap = mps_to_seconds_per_km(split.average_grade_adjusted_speed_mps)
        delta = pace - gap if pace is not None and gap is not None else None
        deltas.append(delta)
        gaps.append(gap)
        rows.append([split.split, format_pace(pace), format_pace(gap), format_optional(delta, "s", 0), format_optional(split.elevation_difference_m, " m", 0)])
    if not rows:
        return "No metric splits are stored for this activity."
    hilliest = max(splits, key=lambda split: abs(split.elevation_difference_m or 0))
    return "\n".join(
        [
            format_table(["split", "pace", "gap", "delta", "elev"], rows),
            f"Mean pace-vs-GAP delta: {format_optional(mean(deltas), ' sec/km', 1)}",
            f"Effort consistency CV from GAP: {format_optional(coefficient_of_variation_pct(gaps), '%', 1)}",
            f"Hilliest split: {hilliest.split} ({format_optional(hilliest.elevation_difference_m, ' m', 0)})",
            "Notes: GAP is Strava's model and should be treated as approximate.",
        ]
    )


def get_activity_hr_zone_distribution_text(db: Session, user: User, activity_id: int) -> str:
    if not queries.require_user_activity(db, user, activity_id):
        return _not_found()
    buckets = queries.get_activity_zone_buckets(db, activity_id)
    if not buckets:
        return "Zone data not ingested for this activity."
    zones = queries.get_latest_athlete_zones(db, user)
    total = sum(bucket.time_seconds or 0 for bucket in buckets)
    rows = [
        [f"Z{bucket.bucket_index}", format_duration(bucket.time_seconds), f"{pct(bucket.time_seconds or 0, total) or 0:.1f}%"]
        for bucket in buckets[:5]
    ]
    return "\n".join([format_zone_boundaries(zones), format_table(["zone", "time", "pct"], rows), f"Total HR-recorded time: {format_duration(total)}"])


def analyze_hr_decoupling_text(db: Session, user: User, activity_id: int) -> str:
    if not queries.require_user_activity(db, user, activity_id):
        return _not_found()
    splits = [
        split
        for split in queries.get_activity_splits(db, activity_id, "metric")
        if split.average_heartrate_bpm is not None and _split_pace(split) is not None
    ]
    body = splits[2:-1] if len(splits) >= 7 else splits
    if len(body) < 6:
        return "Requires at least 6 km of HR-enabled steady running to estimate decoupling."
    midpoint = len(body) // 2
    buckets: dict[int, dict[str, list[float]]] = defaultdict(lambda: {"first": [], "second": []})
    for index, split in enumerate(body):
        pace = _split_pace(split)
        if pace is None or split.average_heartrate_bpm is None:
            continue
        bucket = floor(pace / 10)
        half = "first" if index < midpoint else "second"
        buckets[bucket][half].append(split.average_heartrate_bpm)
    rows = []
    weighted = []
    for bucket, halves in sorted(buckets.items()):
        first = mean(halves["first"])
        second = mean(halves["second"])
        if first is None or second is None:
            continue
        decoupling = (second - first) / first * 100
        count = len(halves["first"]) + len(halves["second"])
        weighted.extend([decoupling] * count)
        rows.append([f"{bucket * 10}-{bucket * 10 + 10}s/km bucket", f"{first:.0f}", f"{second:.0f}", f"{decoupling:+.1f}%"])
    if not rows:
        return "Could not compare matching pace buckets across both halves."
    avg = mean(weighted)
    classification = "strong aerobic durability" if avg is not None and avg < 5 else "acceptable" if avg is not None and avg <= 10 else "high drift"
    return "\n".join([format_table(["pace_bucket", "1st_half_hr", "2nd_half_hr", "decoupling"], rows), f"Weighted average decoupling: {avg:+.1f}% ({classification})", "Notes: split-based decoupling is approximate."])


def get_period_hr_zone_distribution_text(db: Session, user: User, start_date: str, end_date: str, sport_type: str | None = None) -> str:
    start, end = queries.validate_date_range(start_date, end_date)
    if start is None or end is None:
        raise ValueError("start_date and end_date are required")
    rows = queries.list_runs_between(db, user, start=start, end=end, sport_types=queries.normalize_sport_types(sport_type, default_runs=True))
    totals = [0, 0, 0, 0, 0]
    missing = 0
    for activity in rows:
        seconds = _zoned_seconds(queries.get_activity_zone_buckets(db, activity.activity_id))
        if sum(seconds) == 0:
            missing += 1
        totals = [left + right for left, right in zip(totals, seconds)]
    total = sum(totals)
    zone_rows = [[f"Z{index + 1}", format_duration(value), f"{pct(value, total) or 0:.1f}%"] for index, value in enumerate(totals)]
    quality = sum(totals[2:]) / 60
    easy = sum(totals[:2]) / 60
    return "\n".join(
        [
            f"Period: {start} to {end} ({len(rows) - missing} runs with HR zones, {missing} missing)",
            format_table(["zone", "time", "pct"], zone_rows),
            f"Quality minutes (Z3+Z4+Z5): {quality:.1f}",
            f"Easy minutes (Z1+Z2): {easy:.1f}",
            f"Easy/quality ratio: {(easy / quality if quality else 0):.1f}:1",
        ]
    )


def validate_hr_zones_text(db: Session, user: User, lookback_days: int = 60) -> str:
    zones = queries.get_latest_athlete_zones(db, user)
    if not zones:
        return "Athlete heart-rate zones are not cached."
    start = queries.today() - timedelta(days=lookback_days)
    rows = queries.list_runs_between(db, user, start=start, end=queries.today())
    observed_max = max((row.max_heartrate_bpm or 0 for row in rows), default=0)
    z5_floor = zones[4].min_value if len(zones) >= 5 else None
    totals = [0, 0, 0, 0, 0]
    for activity in rows:
        seconds = _zoned_seconds(queries.get_activity_zone_buckets(db, activity.activity_id))
        totals = [left + right for left, right in zip(totals, seconds)]
    easy = sum(totals[:2])
    hard = totals[3] + totals[4]
    ratio = easy / hard if hard else 0
    lines = [format_zone_boundaries(zones), f"Observed max HR over {lookback_days}d: {observed_max:.0f} bpm"]
    if z5_floor:
        if observed_max > z5_floor + 5:
            lines.append("Diagnostic: observed max is well above Z5 floor; zones may be set too low.")
        elif observed_max < z5_floor - 10:
            lines.append("Diagnostic: Z5 has not been approached recently; zones may be high or no max effort was logged.")
        else:
            lines.append("Diagnostic: observed max is consistent with current Z5 floor.")
    lines.append(f"Polarization check Z1+Z2 : Z4+Z5 = {ratio:.1f}:1")
    return "\n".join(lines)


def analyze_cadence_text(db: Session, user: User, activity_id: int) -> str:
    activity = queries.require_user_activity(db, user, activity_id)
    if not activity:
        return _not_found()
    laps = queries.get_activity_laps(db, activity_id)
    if not laps:
        return "No laps are stored for cadence analysis."
    rows = [[lap.lap_index, format_optional(lap.average_cadence_spm, " spm", 0), format_optional((lap.average_cadence_spm or 0) - (activity.average_cadence_spm or 0), " spm", 0)] for lap in laps]
    start = (activity.start_date_local.date() - timedelta(days=30)) if activity.start_date_local else queries.today() - timedelta(days=30)
    baseline = median([row.average_cadence_spm for row in queries.list_runs_between(db, user, start=start, end=queries.today())])
    flag = "lower than your baseline" if baseline and activity.average_cadence_spm and activity.average_cadence_spm < baseline - 3 else "within baseline range"
    return "\n".join([format_table(["lap", "cadence", "delta_from_activity_avg"], rows), f"Cadence drift slope: {format_optional(linear_slope([lap.average_cadence_spm for lap in laps]), ' spm/lap', 1)}", f"30-day baseline: {format_optional(baseline, ' spm', 0)}; activity average is {flag}."])


def get_cadence_trend_text(db: Session, user: User, start_date: str | None = None, end_date: str | None = None, lookback_days: int | None = None) -> str:
    end = queries.parse_iso_date(end_date, "end_date") or queries.today()
    start = queries.parse_iso_date(start_date, "start_date") or (end - timedelta(days=lookback_days or 30))
    rows = [row for row in queries.list_runs_between(db, user, start=start, end=end) if row.average_cadence_spm is not None]
    table = format_table(["date", "distance", "pace", "cadence"], [[format_date(row.start_date_local), format_distance(row.distance_m, 2), format_pace(_pace_for_activity(row)), format_optional(row.average_cadence_spm, " spm", 0)] for row in rows[:50]])
    return "\n".join([table, f"Period mean cadence: {format_optional(mean([row.average_cadence_spm for row in rows]), ' spm', 1)}", f"Trend slope: {format_optional(linear_slope([row.average_cadence_spm for row in rows]), ' spm/run', 2)}"])


def get_elevation_profile_summary_text(db: Session, user: User, activity_id: int) -> str:
    activity = queries.require_user_activity(db, user, activity_id)
    if not activity:
        return _not_found()
    if activity.trainer or activity.total_elevation_gain_m is None:
        return "Treadmill/indoor or missing elevation activity; no terrain summary available."
    splits = queries.get_activity_splits(db, activity_id, "metric")
    distance_km = km(activity.distance_m, 3) or 0
    hilliness = sum(abs(split.elevation_difference_m or 0) for split in splits) / distance_km if distance_km else 0
    hilliest = max(splits, key=lambda split: abs(split.elevation_difference_m or 0), default=None)
    return "\n".join(
        [
            f"Total gain: {format_optional(activity.total_elevation_gain_m, ' m', 0)}, gain per km: {(activity.total_elevation_gain_m or 0) / distance_km if distance_km else 0:.1f} m/km",
            f"Elevation range: {format_optional(activity.elev_low_m, ' m', 1)} to {format_optional(activity.elev_high_m, ' m', 1)}",
            f"Hilliness index: {hilliness:.1f} m/km",
            f"Hilliest split: {('split ' + str(hilliest.split) + ' (' + format_optional(hilliest.elevation_difference_m, ' m', 0) + ')') if hilliest else 'n/a'}",
        ]
    )


def get_activity_best_efforts_text(db: Session, user: User, activity_id: int) -> str:
    if not queries.require_user_activity(db, user, activity_id):
        return _not_found()
    rows = queries.get_activity_best_efforts(db, activity_id)
    if not rows:
        return "No best efforts are stored for this activity."
    return format_table(["name", "distance_m", "time", "pace", "pr_rank"], [[row.name or "", format_optional(row.distance_m, " m", 0), format_duration(row.moving_time_seconds), format_pace(seconds_per_km(row.distance_m, row.moving_time_seconds)), format_optional(row.pr_rank)] for row in rows])


def track_best_effort_progression_text(db: Session, user: User, effort_name: str, lookback_days: int = 365, limit: int = 50) -> str:
    rows = queries.activities_with_best_effort(db, user, effort_name=effort_name, lookback_days=lookback_days, limit=limit)
    if not rows:
        return f"No {effort_name} best efforts found in the selected period."
    table_rows = [[format_date(activity.start_date_local), format_duration(effort.moving_time_seconds), format_pace(seconds_per_km(effort.distance_m, effort.moving_time_seconds)), activity.name or "Untitled"] for activity, effort in rows]
    best = min((effort for _, effort in rows), key=lambda effort: effort.moving_time_seconds or 999999)
    return "\n".join([format_table(["date", "time", "pace", "activity"], table_rows, max_rows=limit), f"Best in period: {format_duration(best.moving_time_seconds)}", f"Trend slope: {format_optional(linear_slope([effort.moving_time_seconds for _, effort in reversed(rows)]), ' sec/run', 1)}"])


def find_pr_activities_text(db: Session, user: User, lookback_days: int = 365) -> str:
    rows = queries.activities_with_best_effort(db, user, lookback_days=lookback_days, pr_only=True, limit=100)
    if not rows:
        return "No PR best efforts found in the selected period."
    grouped: dict[int, list[str]] = defaultdict(list)
    activities: dict[int, StravaActivity] = {}
    for activity, effort in rows:
        activities[activity.activity_id] = activity
        grouped[activity.activity_id].append(f"{effort.name}: {format_duration(effort.moving_time_seconds)}")
    table_rows = [[activity_id, format_date(activities[activity_id].start_date_local), activities[activity_id].name or "Untitled", "; ".join(efforts)] for activity_id, efforts in grouped.items()]
    return format_table(["activity_id", "date", "activity", "PR efforts"], table_rows)


def _period_metrics(db: Session, user: User, start: date, end: date, sport_type: str | None = None) -> dict[str, object]:
    rows = queries.list_runs_between(db, user, start=start, end=end, sport_types=queries.normalize_sport_types(sport_type, default_runs=True))
    total_distance = sum(row.distance_m or 0 for row in rows) / 1000
    total_time = sum(row.moving_time_seconds or 0 for row in rows)
    total_elev = sum(row.total_elevation_gain_m or 0 for row in rows)
    zones = [0, 0, 0, 0, 0]
    for row in rows:
        seconds = _zoned_seconds(queries.get_activity_zone_buckets(db, row.activity_id))
        zones = [left + right for left, right in zip(zones, seconds)]
    return {
        "rows": rows,
        "distance_km": total_distance,
        "moving_time": total_time,
        "run_count": len(rows),
        "longest_km": max((row.distance_m or 0 for row in rows), default=0) / 1000,
        "elev_m": total_elev,
        "avg_hr": mean([row.average_heartrate_bpm for row in rows]),
        "quality_minutes": sum(zones[2:]) / 60,
        "easy_pct": pct(zones[0] + zones[1], sum(zones)) or 0,
        "zones": zones,
    }


def _summary_row(label: str, metrics: dict[str, object]) -> list[object]:
    return [label, f"{metrics['distance_km']:.1f}", format_duration(int(metrics["moving_time"])), metrics["run_count"], f"{metrics['longest_km']:.1f}", f"{metrics['elev_m']:.0f}", format_optional(metrics["avg_hr"], " bpm", 0), f"{metrics['quality_minutes']:.1f}", f"{metrics['easy_pct']:.1f}%"]


def get_weekly_summary_text(db: Session, user: User, weeks: int = 4, week_start: str = "monday") -> str:
    today = queries.today()
    offset = today.weekday() if week_start != "sunday" else (today.weekday() + 1) % 7
    current_start = today - timedelta(days=offset)
    rows = []
    for index in range(min(max(weeks, 1), 26)):
        start = current_start - timedelta(days=index * 7)
        end = start + timedelta(days=6)
        rows.append(_summary_row(f"{start}..{end}", _period_metrics(db, user, start, end)))
    return format_table(["week", "km", "time", "runs", "longest", "elev", "avg_hr", "quality_min", "easy_pct"], rows)


def get_monthly_summary_text(db: Session, user: User, months: int = 6) -> str:
    today = queries.today()
    rows = []
    year, month = today.year, today.month
    for _ in range(min(max(months, 1), 24)):
        start = date(year, month, 1)
        next_month = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
        end = next_month - timedelta(days=1)
        rows.append(_summary_row(start.strftime("%Y-%m"), _period_metrics(db, user, start, end)))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return format_table(["month", "km", "time", "runs", "longest", "elev", "avg_hr", "quality_min", "easy_pct"], rows)


def get_period_summary_text(db: Session, user: User, start_date: str, end_date: str, sport_type: str | None = None) -> str:
    start, end = queries.validate_date_range(start_date, end_date)
    if start is None or end is None:
        raise ValueError("start_date and end_date are required")
    metrics = _period_metrics(db, user, start, end, sport_type)
    classifications = defaultdict(int)
    for row in metrics["rows"]:
        classifications[classify_workout_type_value(db, user, row)[0]] += 1
    return "\n".join([format_table(["period", "km", "time", "runs", "longest", "elev", "avg_hr", "quality_min", "easy_pct"], [_summary_row(f"{start}..{end}", metrics)]), "Workout type counts: " + ", ".join(f"{key}={value}" for key, value in sorted(classifications.items()))])


def get_volume_trend_text(db: Session, user: User, weeks: int = 12) -> str:
    today = queries.today()
    current_start = today - timedelta(days=today.weekday())
    rows = []
    weekly = []
    for index in range(min(max(weeks, 1), 52)):
        start = current_start - timedelta(days=index * 7)
        end = start + timedelta(days=6)
        metrics = _period_metrics(db, user, start, end)
        km_value = metrics["distance_km"]
        weekly.append(km_value)
        previous = weekly[-2] if len(weekly) > 1 else None
        change = ((km_value - previous) / previous * 100) if previous else 0
        rows.append([f"{start}", f"{km_value:.1f}", f"{change:+.1f}%", "flag" if abs(change) > 25 else ""])
    return format_table(["week_start", "weekly_km", "wow_change", "flag"], rows)


def get_intensity_distribution_text(db: Session, user: User, start_date: str, end_date: str) -> str:
    start, end = queries.validate_date_range(start_date, end_date)
    if start is None or end is None:
        raise ValueError("start_date and end_date are required")
    metrics = _period_metrics(db, user, start, end)
    zones = metrics["zones"]
    total = sum(zones)
    if total == 0:
        return "No HR-zone data found for this period."
    low = pct(zones[0] + zones[1], total) or 0
    mid = pct(zones[2], total) or 0
    high = pct(zones[3] + zones[4], total) or 0
    shape = "polarized" if low >= 75 and high >= 15 and mid <= 10 else "threshold-heavy" if mid >= 25 else "low-intensity" if high < 5 else "pyramid/mixed"
    return "\n".join([format_table(["band", "pct"], [["Z1+Z2", f"{low:.1f}%"], ["Z3", f"{mid:.1f}%"], ["Z4+Z5", f"{high:.1f}%"]]), f"Classification: {shape}"])


def get_long_run_progression_text(db: Session, user: User, weeks: int = 12) -> str:
    today = queries.today()
    current_start = today - timedelta(days=today.weekday())
    values = []
    rows = []
    for index in range(min(max(weeks, 1), 52)):
        start = current_start - timedelta(days=index * 7)
        end = start + timedelta(days=6)
        runs = queries.list_runs_between(db, user, start=start, end=end)
        longest = max((row.distance_m or 0 for row in runs), default=0) / 1000
        values.append(longest)
        rows.append([str(start), f"{longest:.1f}", len(runs), "missing week" if not runs else ""])
    return "\n".join([format_table(["week_start", "longest_km", "runs", "note"], rows), f"Trend slope: {format_optional(linear_slope(list(reversed(values))), ' km/week', 2)}"])


def get_pace_at_distance_progression_text(db: Session, user: User, min_distance_km: float, max_distance_km: float, lookback_days: int = 180) -> str:
    start = queries.today() - timedelta(days=lookback_days)
    rows = [row for row in queries.list_runs_between(db, user, start=start, end=queries.today()) if row.distance_m and min_distance_km <= row.distance_m / 1000 <= max_distance_km]
    by_month: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        if row.start_date_local:
            pace = _pace_for_activity(row)
            if pace:
                by_month[row.start_date_local.strftime("%Y-%m")].append(pace)
    table_rows = [[month, format_pace(median(values)), len(values)] for month, values in sorted(by_month.items())]
    return "\n".join([format_table(["month", "median_pace", "runs"], table_rows), f"Trend slope: {format_optional(linear_slope([median(values) for _, values in sorted(by_month.items())]), ' sec/km per month', 1)}"])


def compare_activities_text(db: Session, user: User, activity_id_a: int, activity_id_b: int) -> str:
    a = queries.require_user_activity(db, user, activity_id_a)
    b = queries.require_user_activity(db, user, activity_id_b)
    if not a or not b:
        return _not_found()
    rows = [
        ["distance_km", f"{(km(a.distance_m) or 0):.2f}", f"{(km(b.distance_m) or 0):.2f}", f"{((km(a.distance_m) or 0) - (km(b.distance_m) or 0)):+.2f}"],
        ["duration", format_duration(a.moving_time_seconds), format_duration(b.moving_time_seconds), f"{(a.moving_time_seconds or 0) - (b.moving_time_seconds or 0):+d}s"],
        ["pace", format_pace(_pace_for_activity(a)), format_pace(_pace_for_activity(b)), format_optional((_pace_for_activity(a) or 0) - (_pace_for_activity(b) or 0), "s/km", 0)],
        ["avg_hr", format_optional(a.average_heartrate_bpm, " bpm", 0), format_optional(b.average_heartrate_bpm, " bpm", 0), format_optional((a.average_heartrate_bpm or 0) - (b.average_heartrate_bpm or 0), " bpm", 0)],
        ["cadence", format_optional(a.average_cadence_spm, " spm", 0), format_optional(b.average_cadence_spm, " spm", 0), format_optional((a.average_cadence_spm or 0) - (b.average_cadence_spm or 0), " spm", 0)],
        ["elevation", format_optional(a.total_elevation_gain_m, " m", 0), format_optional(b.total_elevation_gain_m, " m", 0), format_optional((a.total_elevation_gain_m or 0) - (b.total_elevation_gain_m or 0), " m", 0)],
    ]
    return format_table(["metric", "A", "B", "delta"], rows)


def compare_periods_text(db: Session, user: User, period_a_start: str, period_a_end: str, period_b_start: str, period_b_end: str) -> str:
    a_start, a_end = queries.validate_date_range(period_a_start, period_a_end)
    b_start, b_end = queries.validate_date_range(period_b_start, period_b_end)
    if None in (a_start, a_end, b_start, b_end):
        raise ValueError("all period dates are required")
    a = _period_metrics(db, user, a_start, a_end)
    b = _period_metrics(db, user, b_start, b_end)
    rows = [
        ["distance_km", f"{a['distance_km']:.1f}", f"{b['distance_km']:.1f}", f"{a['distance_km'] - b['distance_km']:+.1f}"],
        ["moving_time", format_duration(int(a["moving_time"])), format_duration(int(b["moving_time"])), f"{int(a['moving_time']) - int(b['moving_time']):+d}s"],
        ["run_count", a["run_count"], b["run_count"], int(a["run_count"]) - int(b["run_count"])],
        ["quality_minutes", f"{a['quality_minutes']:.1f}", f"{b['quality_minutes']:.1f}", f"{a['quality_minutes'] - b['quality_minutes']:+.1f}"],
        ["easy_pct", f"{a['easy_pct']:.1f}%", f"{b['easy_pct']:.1f}%", f"{a['easy_pct'] - b['easy_pct']:+.1f}%"],
    ]
    return format_table(["metric", "period_a", "period_b", "delta"], rows)


def compare_to_similar_recent_runs_text(db: Session, user: User, activity_id: int, lookback_days: int = 90, n_similar: int = 5) -> str:
    reference, scored = queries.find_similar_user_runs(db, user, activity_id, lookback_days=lookback_days, limit=n_similar)
    if not reference:
        return _not_found()
    if len(scored) < 3:
        return "Insufficient comparables: fewer than 3 similar runs found."
    comps = [row for row, _ in scored]
    rows = [
        ["pace", format_pace(_pace_for_activity(reference)), format_pace(median([_pace_for_activity(row) for row in comps])), format_optional((_pace_for_activity(reference) or 0) - (median([_pace_for_activity(row) for row in comps]) or 0), "s/km", 0)],
        ["avg_hr", format_optional(reference.average_heartrate_bpm, " bpm", 0), format_optional(median([row.average_heartrate_bpm for row in comps]), " bpm", 0), ""],
        ["cadence", format_optional(reference.average_cadence_spm, " spm", 0), format_optional(median([row.average_cadence_spm for row in comps]), " spm", 0), ""],
        ["elev_gain", format_optional(reference.total_elevation_gain_m, " m", 0), format_optional(median([row.total_elevation_gain_m for row in comps]), " m", 0), ""],
    ]
    return format_table(["metric", "reference", "similar_median", "delta"], rows)


def get_recovery_status_text(db: Session, user: User, as_of_date: str | None = None) -> str:
    as_of = queries.parse_iso_date(as_of_date, "as_of_date") or queries.today()
    rows = queries.list_runs_between(db, user, start=as_of - timedelta(days=28), end=as_of)
    last_run = max((row for row in rows if row.start_date_local), key=lambda row: row.start_date_local, default=None)
    hard_runs = [row for row in rows if classify_workout_type_value(db, user, row)[0] in ("intervals", "tempo", "race")]
    last_hard = max((row for row in hard_runs if row.start_date_local), key=lambda row: row.start_date_local, default=None)
    last_7d = sum(row.distance_m or 0 for row in rows if row.start_date_local and row.start_date_local.date() >= as_of - timedelta(days=7)) / 1000
    last_28d = sum(row.distance_m or 0 for row in rows) / 1000
    return "\n".join(
        [
            f"Days since last run: {(as_of - last_run.start_date_local.date()).days if last_run and last_run.start_date_local else 'unknown'}",
            f"Days since last hard run: {(as_of - last_hard.start_date_local.date()).days if last_hard and last_hard.start_date_local else 'unknown'}",
            f"Last 7d: {last_7d:.1f} km. 4wk weekly avg: {last_28d / 4:.1f} km. Delta: {((last_7d / (last_28d / 4) - 1) * 100) if last_28d else 0:+.0f}%.",
        ]
    )


def compute_acute_chronic_ratio_text(db: Session, user: User, as_of_date: str | None = None, metric: str = "distance") -> str:
    as_of = queries.parse_iso_date(as_of_date, "as_of_date") or queries.today()
    rows = queries.list_runs_between(db, user, start=as_of - timedelta(days=28), end=as_of)
    value = (lambda row: row.moving_time_seconds or 0) if metric == "duration" else (lambda row: row.distance_m or 0)
    acute = sum(value(row) for row in rows if row.start_date_local and row.start_date_local.date() >= as_of - timedelta(days=7))
    chronic = sum(value(row) for row in rows) / 4
    acwr = acute / chronic if chronic else 0
    classification = "sweet spot" if 0.8 <= acwr <= 1.3 else "undertrained" if acwr < 0.8 else "caution" if acwr <= 1.5 else "injury-risk flag"
    unit = "seconds" if metric == "duration" else "metres"
    return f"acute: {acute:.0f} {unit}\nchronic: {chronic:.0f} {unit}/week\nacwr: {acwr:.2f}\nclassification: {classification}"


def detect_training_red_flags_text(db: Session, user: User, lookback_weeks: int = 4) -> str:
    flags = []
    today = queries.today()
    current_start = today - timedelta(days=today.weekday())
    weekly = []
    for index in range(lookback_weeks + 4):
        start = current_start - timedelta(days=index * 7)
        end = start + timedelta(days=6)
        weekly.append(_period_metrics(db, user, start, end)["distance_km"])
    for index, value in enumerate(weekly[:lookback_weeks]):
        baseline = mean(weekly[index + 1:index + 5])
        if baseline and value > 1.4 * baseline:
            flags.append(f"Volume ramp: week {index + 1} distance {value:.1f} km > 1.4x trailing baseline {baseline:.1f} km")
    rows = queries.list_runs_between(db, user, start=today - timedelta(days=14), end=today)
    if rows:
        active_dates = {row.start_date_local.date() for row in rows if row.start_date_local}
        if len(active_dates) >= 14:
            flags.append("No rest days: 14 consecutive logged run days.")
    if not flags:
        return "All clear: no training red flags triggered by the stored data."
    return "Triggered red flags:\n" + "\n".join(f"- {flag}" for flag in flags)


def check_data_availability_text(
    db: Session,
    user: User,
    activity_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    if activity_id is not None:
        activity = queries.require_user_activity(db, user, activity_id)
        if not activity:
            return _not_found()
        counts = queries.count_child_rows(db, activity_id)
        return "\n".join(
            [
                f"Activity {activity_id} availability:",
                f"- has_heartrate: {activity.has_heartrate}",
                f"- laps: {counts['laps']}",
                f"- splits_metric: {counts['splits_metric']}",
                f"- splits_standard: {counts['splits_standard']}",
                f"- best_efforts: {counts['best_efforts']}",
                "- segments: unavailable (segment-effort table is not in current schema)",
                f"- zones: {counts['zones']}",
            ]
        )
    start, end = queries.validate_date_range(start_date, end_date)
    if start is None or end is None:
        raise ValueError("provide either activity_id or start_date and end_date")
    rows = queries.list_runs_between(db, user, start=start, end=end)
    missing_dates = queries.missing_run_dates(rows, start, end)
    missing_hr = sum(1 for row in rows if not row.has_heartrate)
    missing_laps = sum(1 for row in rows if not row.has_laps)
    missing_zones = sum(1 for row in rows if not row.has_zones)
    return "\n".join(
        [
            f"Range {start} to {end} availability:",
            f"- activities: {len(rows)}",
            f"- missing_hr: {missing_hr}",
            f"- missing_laps: {missing_laps}",
            f"- missing_zones: {missing_zones}",
            f"- zero-activity dates: {', '.join(str(day) for day in missing_dates[:30]) or 'none'}",
        ]
    )


def find_similar_runs_text(
    db: Session,
    user: User,
    reference_activity_id: int,
    lookback_days: int = 90,
    distance_tolerance_pct: float = 15,
    elev_tolerance_pct: float = 25,
    elev_tolerance_abs_m: float = 50,
    limit: int = 10,
) -> str:
    reference, scored = queries.find_similar_user_runs(
        db,
        user,
        reference_activity_id,
        lookback_days=lookback_days,
        distance_tolerance_pct=distance_tolerance_pct,
        elev_tolerance_pct=elev_tolerance_pct,
        elev_tolerance_abs_m=elev_tolerance_abs_m,
        limit=limit,
    )
    if not reference:
        return _not_found()
    if not scored:
        return "No similar runs found for the selected tolerances."
    rows = []
    for activity, score in scored:
        rows.append(
            [
                activity.activity_id,
                format_date(activity.start_date_local),
                format_distance(activity.distance_m, 3),
                format_optional(activity.total_elevation_gain_m, " m", 0),
                format_duration(activity.moving_time_seconds),
                format_pace(_pace_for_activity(activity)),
                format_optional(activity.average_heartrate_bpm, " bpm", 0),
                classify_workout_type_value(db, user, activity)[0],
                f"{score:.1f}",
            ]
        )
    return format_table(["activity_id", "date", "distance", "elev", "duration", "pace", "avg_hr", "type", "score"], rows)
