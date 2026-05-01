from __future__ import annotations

from datetime import date, datetime

from app.models import StravaActivity, StravaActivityMetric


def format_date(value: date | datetime | None) -> str:
    if value is None:
        return "unknown date"
    return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()


def format_distance(meters: float | None) -> str:
    if meters is None:
        return "unknown distance"
    return f"{meters / 1000:.2f} km"


def format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "unknown duration"
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    return f"{minutes}m {secs:02d}s"


def format_activity_list(rows: list[StravaActivity]) -> str:
    if not rows:
        return "No activities found for that filter."

    lines = [f"Found {len(rows)} activities:"]
    for row in rows:
        sport = row.sport_type or row.activity_type or "unknown sport"
        lines.append(
            "- "
            f"{row.activity_id}: {format_date(row.start_date_local)} - {row.name or 'Untitled activity'} "
            f"({sport}, {format_distance(row.distance_m)}, moving {format_duration(row.moving_time_seconds)}, "
            f"elevation {row.total_elevation_gain_m or 0:.0f} m"
            f"{', avg HR ' + str(round(row.average_heartrate_bpm)) + ' bpm' if row.average_heartrate_bpm else ''}"
            f"{', avg watts ' + str(round(row.average_watts)) if row.average_watts else ''})"
        )
    return "\n".join(lines)


def format_activity_detail(row: StravaActivity, metrics: StravaActivityMetric | None = None) -> str:
    sport = row.sport_type or row.activity_type or "unknown sport"
    lines = [
        f"Activity {row.activity_id}: {row.name or 'Untitled activity'}",
        f"- Date: {format_date(row.start_date_local)}",
        f"- Sport: {sport}",
        f"- Distance: {format_distance(row.distance_m)}",
        f"- Moving time: {format_duration(row.moving_time_seconds)}",
        f"- Elapsed time: {format_duration(row.elapsed_time_seconds)}",
        f"- Elevation gain: {row.total_elevation_gain_m or 0:.0f} m",
    ]
    if row.average_heartrate_bpm:
        lines.append(f"- Average HR: {row.average_heartrate_bpm:.0f} bpm")
    if row.max_heartrate_bpm:
        lines.append(f"- Max HR: {row.max_heartrate_bpm:.0f} bpm")
    if row.average_watts:
        lines.append(f"- Average watts: {row.average_watts:.0f}")
    if row.weighted_average_watts:
        lines.append(f"- Weighted average watts: {row.weighted_average_watts:.0f}")
    if metrics and metrics.pace_seconds_per_km:
        lines.append(f"- Pace: {format_duration(round(metrics.pace_seconds_per_km))} per km")
    if metrics and metrics.average_speed_kmh:
        lines.append(f"- Average speed: {metrics.average_speed_kmh:.1f} km/h")
    if row.gear_id:
        lines.append(f"- Gear ID: {row.gear_id}")
    lines.extend(
        [
            "- Available detail: "
            f"laps={row.has_laps}, splits={row.has_splits}, best_efforts={row.has_best_efforts}, "
            f"zones={row.has_zones}, gap={row.has_gap}",
            "- Raw Strava detail JSON is intentionally not returned by this PoC tool.",
        ]
    )
    return "\n".join(lines)
