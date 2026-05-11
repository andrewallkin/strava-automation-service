from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date, datetime
from math import sqrt

from app.models import StravaActivity, StravaActivityMetric, StravaAthleteZone

RUN_SPORT_TYPES = ("Run", "TrailRun", "TreadmillRun", "VirtualRun")


def is_run_sport(sport_type: str | None) -> bool:
    return sport_type in RUN_SPORT_TYPES or bool(sport_type and "Run" in sport_type)


def format_date(value: date | datetime | None) -> str:
    if value is None:
        return "unknown date"
    return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()


def km(meters: float | None, digits: int = 3) -> float | None:
    if meters is None:
        return None
    return round(meters / 1000, digits)


def format_distance(meters: float | None, digits: int = 2) -> str:
    value = km(meters, digits)
    if value is None:
        return "unknown distance"
    return f"{value:.{digits}f} km"


def format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "unknown duration"
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def seconds_per_km(distance_m: float | None, seconds: int | float | None) -> float | None:
    if not distance_m or distance_m <= 0 or seconds is None:
        return None
    return float(seconds) / (distance_m / 1000)


def mps_to_seconds_per_km(value: float | None) -> float | None:
    if not value or value <= 0:
        return None
    return 1000 / value


def mps_to_kmh(value: float | None) -> float | None:
    return value * 3.6 if value is not None else None


def format_pace(seconds: float | None) -> str:
    if seconds is None or seconds <= 0:
        return "unknown pace"
    rounded = int(round(seconds))
    minutes, secs = divmod(rounded, 60)
    return f"{minutes}:{secs:02d}/km"


def format_speed(mps: float | None) -> str:
    kmh = mps_to_kmh(mps)
    return "unknown speed" if kmh is None else f"{kmh:.1f} km/h"


def format_optional(value: object, suffix: str = "", digits: int = 0) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}f}{suffix}"
    return f"{value}{suffix}"


def pct(numerator: float | int | None, denominator: float | int | None) -> float | None:
    if numerator is None or not denominator:
        return None
    return numerator / denominator * 100


def mean(values: Iterable[float | int | None]) -> float | None:
    cleaned = [float(value) for value in values if value is not None]
    if not cleaned:
        return None
    return sum(cleaned) / len(cleaned)


def median(values: Iterable[float | int | None]) -> float | None:
    cleaned = sorted(float(value) for value in values if value is not None)
    if not cleaned:
        return None
    midpoint = len(cleaned) // 2
    if len(cleaned) % 2:
        return cleaned[midpoint]
    return (cleaned[midpoint - 1] + cleaned[midpoint]) / 2


def stdev(values: Iterable[float | int | None]) -> float | None:
    cleaned = [float(value) for value in values if value is not None]
    if len(cleaned) < 2:
        return None
    avg = sum(cleaned) / len(cleaned)
    variance = sum((value - avg) ** 2 for value in cleaned) / (len(cleaned) - 1)
    return sqrt(variance)


def coefficient_of_variation_pct(values: Iterable[float | int | None]) -> float | None:
    cleaned = [float(value) for value in values if value is not None]
    avg = mean(cleaned)
    sd = stdev(cleaned)
    if avg is None or avg == 0 or sd is None:
        return None
    return sd / avg * 100


def linear_slope(values: Sequence[float | int | None]) -> float | None:
    points = [(index + 1, float(value)) for index, value in enumerate(values) if value is not None]
    if len(points) < 2:
        return None
    x_mean = sum(point[0] for point in points) / len(points)
    y_mean = sum(point[1] for point in points) / len(points)
    denominator = sum((x - x_mean) ** 2 for x, _ in points)
    if denominator == 0:
        return None
    return sum((x - x_mean) * (y - y_mean) for x, y in points) / denominator


def format_table(headers: Sequence[str], rows: Sequence[Sequence[object]], *, max_rows: int | None = None) -> str:
    visible_rows = rows[:max_rows] if max_rows else rows
    if not visible_rows:
        return "No rows."
    string_rows = [[str(value) for value in row] for row in visible_rows]
    widths = [
        max(len(str(header)), *(len(row[index]) for row in string_rows))
        for index, header in enumerate(headers)
    ]
    lines = [
        " | ".join(str(header).ljust(widths[index]) for index, header in enumerate(headers)),
        " | ".join("-" * width for width in widths),
    ]
    for row in string_rows:
        lines.append(" | ".join(value.ljust(widths[index]) for index, value in enumerate(row)))
    if max_rows and len(rows) > max_rows:
        lines.append(f"... {len(rows) - max_rows} more rows omitted.")
    return "\n".join(lines)


def format_zone_boundaries(zones: Sequence[StravaAthleteZone]) -> str:
    if not zones:
        return "Zones used: athlete HR zones are not cached."
    labels = ["Z1 recovery", "Z2 endurance", "Z3 tempo", "Z4 threshold", "Z5 VO2max"]
    parts = []
    for index, zone in enumerate(zones[:5]):
        label = labels[index] if index < len(labels) else f"Z{zone.bucket_index}"
        min_value = zone.min_value
        max_value = zone.max_value
        if min_value in (None, 0) and max_value is not None:
            boundary = f"< {max_value:.0f} bpm"
        elif max_value in (None, -1):
            boundary = f">= {min_value:.0f} bpm" if min_value is not None else "open"
        else:
            boundary = f"{min_value:.0f}-{max_value:.0f} bpm"
        parts.append(f"{label}: {boundary}")
    custom = zones[0].custom_zones if zones else None
    custom_text = f"; custom_zones: {str(custom).lower()}" if custom is not None else ""
    return "Zones used: " + ", ".join(parts) + custom_text


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
            f"pace {format_pace(seconds_per_km(row.distance_m, row.moving_time_seconds))}, "
            f"elevation {row.total_elevation_gain_m or 0:.0f} m"
            f"{', avg HR ' + str(round(row.average_heartrate_bpm)) + ' bpm' if row.average_heartrate_bpm else ''}"
            f")"
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
