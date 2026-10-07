from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.mcp.formatting import is_run_sport

JOHANNESBURG = ZoneInfo("Africa/Johannesburg")
STRENGTH_SPORTS = {"WeightTraining", "Workout"}
UNKNOWN_SPORT_TYPE = "Unknown"
INJURY_PATTERNS = (
    ("shin", re.compile(r"shin", re.IGNORECASE)),
    ("IT", re.compile(r"\bIT\b", re.IGNORECASE)),
    ("knee", re.compile(r"knee", re.IGNORECASE)),
)


def type_group(sport_type: str | None) -> str:
    if is_run_sport(sport_type):
        return "run"
    if sport_type in STRENGTH_SPORTS:
        return "strength"
    return "other"


def local_today(now: datetime | None = None) -> date:
    moment = now or datetime.now(JOHANNESBURG)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=JOHANNESBURG)
    return moment.astimezone(JOHANNESBURG).date()


def monday_on_or_before(value: date) -> date:
    return value - timedelta(days=value.weekday())


@dataclass
class StatActivity:
    activity_id: int
    sport_type: str | None
    local_date: date
    start_local: datetime
    distance_m: float | None
    moving_time_seconds: int | None
    elevation_gain_m: float | None
    average_cadence_spm: float | None
    has_heartrate: bool
    hr_zones: tuple[int, int, int, int, int]
    description: str | None
    elapsed_time_seconds: int | None = None


def _in_window(activity: StatActivity, start: date, end: date) -> bool:
    return start <= activity.local_date <= end


def _pace(distance_m: float | None, moving_time: int | None) -> int | None:
    if not distance_m or distance_m <= 0 or moving_time is None:
        return None
    return round(moving_time / (distance_m / 1000))


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def by_sport_type(rows: list[StatActivity]) -> dict[str, dict]:
    grouped: dict[str, list[StatActivity]] = defaultdict(list)
    for row in rows:
        grouped[row.sport_type or UNKNOWN_SPORT_TYPE].append(row)
    return {
        sport: {
            "activityCount": len(items),
            "distanceM": round(sum(item.distance_m or 0 for item in items), 1),
            "movingTimeSec": sum(item.moving_time_seconds or 0 for item in items),
            "elapsedTimeSec": sum(item.elapsed_time_seconds or 0 for item in items),
            "elevationGainM": round(sum(item.elevation_gain_m or 0 for item in items), 1),
            "days": sorted({item.local_date.isoformat() for item in items}),
        }
        for sport, items in sorted(grouped.items())
    }


def summarize_window(
    activities: list[StatActivity],
    start: date,
    end: date,
    previous: dict | None,
) -> dict:
    rows = [row for row in activities if _in_window(row, start, end)]
    runs = [row for row in rows if type_group(row.sport_type) == "run"]
    strength = [row for row in rows if type_group(row.sport_type) == "strength"]
    other_count = sum(1 for row in rows if type_group(row.sport_type) == "other")

    distance = sum(row.distance_m or 0 for row in runs)
    moving = sum(row.moving_time_seconds or 0 for row in runs)
    elevation = sum(row.elevation_gain_m or 0 for row in runs)
    longest = max(runs, key=lambda row: row.distance_m or 0) if runs else None
    zones = [0, 0, 0, 0, 0]
    for row in runs:
        for index, seconds in enumerate(row.hr_zones):
            zones[index] += seconds
    zone_total = sum(zones)
    easy = zones[0] + zones[1]
    cadence_values = [row.average_cadence_spm for row in runs if row.average_cadence_spm is not None]
    run_dates = sorted({row.local_date.isoformat() for row in runs})
    strength_dates = sorted({row.local_date.isoformat() for row in strength})

    by_date: dict[date, list[StatActivity]] = defaultdict(list)
    for row in rows:
        by_date[row.local_date].append(row)
    same_day = []
    for day, day_rows in sorted(by_date.items()):
        day_runs = [row for row in day_rows if type_group(row.sport_type) == "run"]
        day_strength = [row for row in day_rows if type_group(row.sport_type) == "strength"]
        for run in day_runs:
            for lift in day_strength:
                same_day.append(
                    {
                        "date": day.isoformat(),
                        "runId": run.activity_id,
                        "strengthId": lift.activity_id,
                        "runFirst": run.start_local <= lift.start_local,
                    }
                )

    occupied = {row.local_date for row in runs} | {row.local_date for row in strength}
    day_count = (end - start).days + 1
    rest_days = day_count - len(occupied)

    previous_distance = previous["run"]["distanceM"] if previous else 0
    previous_long = previous["run"]["longestRunM"] if previous else 0
    wow = None
    if previous and previous_distance > 0:
        wow = round((distance - previous_distance) / previous_distance * 100, 1)

    flags = []
    if previous and previous_distance > 0 and distance > previous_distance * 1.10:
        flags.append("volume_jump_high")
    if previous and previous_long > 0 and longest and (longest.distance_m or 0) > previous_long * 1.10:
        flags.append("long_run_jump_high")
    if zone_total and (zones[2] + zones[3] + zones[4]) / zone_total > 0.10:
        flags.append("intensity_creep")
    if any(not pair["runFirst"] for pair in same_day):
        flags.append("run_after_legs")
    if len(run_dates) >= 6:
        flags.append("high_frequency_no_rest")
    if any(not row.has_heartrate for row in runs):
        flags.append("missing_hr")

    weighted_pace_num = 0.0
    weighted_pace_den = 0.0
    for row in runs:
        pace = _pace(row.distance_m, row.moving_time_seconds)
        if pace is None or not row.distance_m:
            continue
        weighted_pace_num += pace * row.distance_m
        weighted_pace_den += row.distance_m

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "run": {
            "activityCount": len(runs),
            "distanceM": round(distance, 1),
            "movingTimeSec": moving,
            "elevationGainM": round(elevation, 1),
            "longestRunM": round(longest.distance_m or 0, 1) if longest else 0,
            "longestRunId": longest.activity_id if longest else None,
            "averagePaceSecPerKm": round(weighted_pace_num / weighted_pace_den) if weighted_pace_den else None,
            "timeInHrZoneSeconds": {str(index + 1): zones[index] for index in range(5)},
            "percentEasyHr": round(easy / zone_total * 100, 1) if zone_total else None,
            "averageCadenceSpm": round(_mean(cadence_values), 1) if cadence_values else None,
            "daysRun": run_dates,
        },
        "strength": {
            "activityCount": len(strength),
            "movingTimeSec": sum(row.moving_time_seconds or 0 for row in strength),
            "days": strength_dates,
            "sameDayAsRun": same_day,
        },
        "other": {"activityCount": other_count},
        "bySportType": by_sport_type(rows),
        "restDays": rest_days,
        "weekOverWeekDistancePct": wow,
        "flags": flags,
    }


def weekly_periods(weeks: int, today: date) -> list[tuple[date, date]]:
    count = min(max(weeks, 1), 26)
    current = monday_on_or_before(today)
    periods = []
    for index in range(count):
        start = current - timedelta(days=7 * index)
        periods.append((start, start + timedelta(days=6)))
    return list(reversed(periods))


def range_periods(start: date, end: date, group_by: str) -> list[tuple[date, date]]:
    if group_by == "day":
        periods = []
        cursor = start
        while cursor <= end:
            periods.append((cursor, cursor))
            cursor += timedelta(days=1)
        return periods
    if group_by == "month":
        periods = []
        cursor = date(start.year, start.month, 1)
        while cursor <= end:
            if cursor.month == 12:
                next_month = date(cursor.year + 1, 1, 1)
            else:
                next_month = date(cursor.year, cursor.month + 1, 1)
            period_start = max(cursor, start)
            period_end = min(next_month - timedelta(days=1), end)
            periods.append((period_start, period_end))
            cursor = next_month
        return periods
    periods = []
    cursor = monday_on_or_before(start)
    while cursor <= end:
        period_start = max(cursor, start)
        period_end = min(cursor + timedelta(days=6), end)
        periods.append((period_start, period_end))
        cursor += timedelta(days=7)
    return periods


def previous_window(start: date, end: date, group_by: str) -> tuple[date, date]:
    if group_by == "day":
        return start - timedelta(days=1), start - timedelta(days=1)
    if group_by == "month":
        previous_end = date(start.year, start.month, 1) - timedelta(days=1)
        return date(previous_end.year, previous_end.month, 1), previous_end
    length = (end - start).days + 1
    previous_end = start - timedelta(days=1)
    return previous_end - timedelta(days=length - 1), previous_end


def rollup(
    activities: list[StatActivity],
    periods: list[tuple[date, date]],
    group_by: str,
) -> list[dict]:
    results = []
    previous = None
    if periods:
        prev_start, prev_end = previous_window(periods[0][0], periods[0][1], group_by)
        previous = summarize_window(activities, prev_start, prev_end, None)
    for start, end in periods:
        current = summarize_window(activities, start, end, previous)
        results.append(current)
        previous = current
    return results


def consistency(activities: list[StatActivity], today: date) -> dict:
    start = today - timedelta(days=27)
    rows = [row for row in activities if _in_window(row, start, today)]
    runs = [row for row in rows if type_group(row.sport_type) == "run"]
    strength = [row for row in rows if type_group(row.sport_type) == "strength"]
    run_dates = {row.local_date for row in runs}
    cursor = today if today in run_dates else today - timedelta(days=1)
    streak = 0
    if cursor in run_dates:
        while cursor in run_dates:
            streak += 1
            cursor -= timedelta(days=1)
    distance = sum(row.distance_m or 0 for row in runs)
    longest = max((row.distance_m or 0 for row in runs), default=0)
    notes = " ".join(row.description or "" for row in runs)
    keywords = [label for label, pattern in INJURY_PATTERNS if pattern.search(notes)]
    return {
        "currentRunStreakDays": streak,
        "runsLast28Days": len(runs),
        "strengthSessionsLast28Days": len(strength),
        "averageWeeklyDistanceM28d": round(distance / 4, 1),
        "averageWeeklyRuns28d": round(len(runs) / 4, 2),
        "longestRun28dM": round(longest, 1),
        "injuryFlagKeywordsInNotes": keywords,
        "activitiesBySportType28d": {sport: totals["activityCount"] for sport, totals in by_sport_type(rows).items()},
    }
