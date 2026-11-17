"""Pure formatters for Telegram command and activity messages."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.time_formatting import format_clock_duration

RUN_TYPES = {"Run", "VirtualRun", "TrailRun", "TreadmillRun", "TrackRun"}
DAY_LABELS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


@dataclass(frozen=True)
class WeekActivity:
    name: str
    sport_type: str
    start: datetime
    distance_m: float
    moving_s: int


def format_pace(distance_m: float, moving_s: float) -> str:
    if distance_m <= 0:
        return "0:00/km"
    seconds_per_km = moving_s / (distance_m / 1000)
    minutes = int(seconds_per_km // 60)
    seconds = int(seconds_per_km % 60)
    return f"{minutes}:{seconds:02d}/km"


def format_run_card(activity: dict) -> str:
    name = activity.get("name") or "Activity"
    distance_m = float(activity.get("distance") or 0)
    moving_s = float(activity.get("moving_time") or 0)
    lines = [
        f"📝 {name}",
        f"📏 {distance_m / 1000:.2f} km",
        f"⏱ {format_clock_duration(moving_s)}",
        f"🏃 {format_pace(distance_m, moving_s)}",
    ]
    average_hr = activity.get("average_heartrate")
    max_hr = activity.get("max_heartrate")
    if average_hr is not None and max_hr is not None:
        lines.append(f"❤️ {int(average_hr)} avg / {int(max_hr)} max")
    cadence = activity.get("average_cadence")
    if cadence:
        lines.append(f"🦶 {int(float(cadence) * 2)} spm")
    elevation = activity.get("total_elevation_gain") or 0
    if elevation:
        lines.append(f"⛰️ {int(elevation)} m")
    lines.extend(["", "Which shoes did you wear? 👟"])
    return "\n".join(lines)


def format_activity_receipt(activity: dict) -> str:
    sport = activity.get("sport_type") or activity.get("type") or "Activity"
    name = activity.get("name") or "Activity"
    distance_m = float(activity.get("distance") or 0)
    moving_s = float(activity.get("moving_time") or 0)
    duration = format_clock_duration(moving_s)
    detail = f"{distance_m / 1000:.2f} km · {duration}" if distance_m > 0 else duration
    return f"{sport}\n{name}\n{detail}"


def _week_header(start: date, end: date) -> str:
    if start.year != end.year:
        return f"📅 {start.day} {start.strftime('%b')} {start.year}–{end.day} {end.strftime('%b')} {end.year}"
    if start.month != end.month:
        return f"📅 {start.day} {start.strftime('%b')}–{end.day} {end.strftime('%b')}"
    return f"📅 {start.day}–{end.day} {end.strftime('%b')}"


def _week_activity_line(activity: WeekActivity) -> str:
    if activity.sport_type in RUN_TYPES and activity.distance_m > 0:
        km = activity.distance_m / 1000
        return f"{activity.name} · {km:.1f} km · {format_pace(activity.distance_m, activity.moving_s)}"
    return f"{activity.name} · {format_clock_duration(activity.moving_s)}"


def format_week(start: date, activities: list[WeekActivity], previous_km: float) -> str:
    grouped: dict[int, list[WeekActivity]] = {index: [] for index in range(7)}
    for activity in activities:
        offset = (activity.start.date() - start).days
        if 0 <= offset <= 6:
            grouped[offset].append(activity)

    lines = [_week_header(start, start + timedelta(days=6)), ""]
    total_distance_m = 0.0
    total_moving_s = 0
    for index, label in enumerate(DAY_LABELS):
        runs = sorted(
            (item for item in grouped[index] if item.sport_type in RUN_TYPES),
            key=lambda item: item.start,
        )
        others = sorted(
            (item for item in grouped[index] if item.sport_type not in RUN_TYPES),
            key=lambda item: item.start,
        )
        ordered = runs + others
        if not ordered:
            lines.append(f"{label}  —")
            continue
        for position, activity in enumerate(ordered):
            body = _week_activity_line(activity)
            lines.append(f"{label}  {body}" if position == 0 else f"     {body}")
            total_distance_m += activity.distance_m
            total_moving_s += activity.moving_s

    this_km = total_distance_m / 1000
    delta = this_km - previous_km
    lines.extend(["", f"{this_km:.1f} km · {format_clock_duration(total_moving_s)}"])
    if abs(delta) < 0.05:
        lines.append("Same distance as last week")
    elif delta > 0:
        lines.append(f"📈 {delta:.1f} km more than last week")
    else:
        lines.append(f"📉 {abs(delta):.1f} km less than last week")
    return "\n".join(lines)


def format_shoe_line(name: str, distance_m: float, notification_distance_m: float | None) -> str:
    km = distance_m / 1000
    flag = ""
    if notification_distance_m is not None and distance_m >= notification_distance_m:
        flag = "replace"
    elif km >= 800:
        flag = "replace"
    elif km >= 600:
        flag = "consider replacement"
    line = f"{name} · {km:.1f} km"
    if flag:
        line = f"{line} · {flag}"
    return line


def format_recent_line(sport_type: str, name: str, distance_m: float, moving_s: int) -> str:
    if sport_type in RUN_TYPES and distance_m > 0:
        return f"{sport_type} · {name} · {distance_m / 1000:.1f} km · {format_pace(distance_m, moving_s)}"
    if distance_m > 0:
        return f"{sport_type} · {name} · {distance_m / 1000:.1f} km · {format_clock_duration(moving_s)}"
    return f"{sport_type} · {name} · {format_clock_duration(moving_s)}"


def format_streak(days: int) -> str:
    if days <= 0:
        return "No current run streak."
    return f"{days}-day run streak"


def format_help() -> str:
    return "\n".join(["/shoes", "/week", "/recent", "/streak", "/help", "/cancel"])
