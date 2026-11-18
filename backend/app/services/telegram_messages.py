"""Pure formatters for Telegram command and activity messages."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.time_formatting import format_clock_duration

RUN_TYPES = {"Run", "VirtualRun", "TrailRun", "TreadmillRun", "TrackRun"}
DAY_LABELS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
SPORT_EMOJI = {
    "Run": "🏃",
    "VirtualRun": "🏃",
    "TrailRun": "🏃",
    "TreadmillRun": "🏃",
    "TrackRun": "🏃",
    "WeightTraining": "🏋️",
    "Ride": "🚴",
    "VirtualRide": "🚴",
    "EBikeRide": "🚴",
    "MountainBikeRide": "🚴",
    "GravelRide": "🚴",
    "Swim": "🏊",
    "Walk": "🚶",
    "Hike": "🥾",
    "Yoga": "🧘",
}


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


def _sport_emoji(sport_type: str) -> str:
    return SPORT_EMOJI.get(sport_type, "•")


def _activity_stats(sport_type: str, distance_m: float, moving_s: float) -> str:
    if sport_type in RUN_TYPES and distance_m > 0:
        km = distance_m / 1000
        return f"{km:.1f} km · {format_pace(distance_m, moving_s)}"
    if distance_m > 0:
        return f"{distance_m / 1000:.1f} km · {format_clock_duration(moving_s)}"
    return format_clock_duration(moving_s)


def _activity_block(sport_type: str, name: str, distance_m: float, moving_s: float) -> str:
    return f"{_sport_emoji(sport_type)} {name}\n{_activity_stats(sport_type, distance_m, moving_s)}"


def _empty_day_span(start_index: int, end_index: int) -> str:
    if start_index == end_index:
        return f"{DAY_LABELS[start_index]} —"
    return f"{DAY_LABELS[start_index]}–{DAY_LABELS[end_index]} —"


def format_week(start: date, activities: list[WeekActivity], previous_km: float) -> str:
    grouped: dict[int, list[WeekActivity]] = {index: [] for index in range(7)}
    for activity in activities:
        offset = (activity.start.date() - start).days
        if 0 <= offset <= 6:
            grouped[offset].append(activity)

    lines = [_week_header(start, start + timedelta(days=6)), ""]
    total_distance_m = 0.0
    total_moving_s = 0
    empty_start: int | None = None
    for index in range(7):
        ordered = sorted(grouped[index], key=lambda item: item.start)
        if not ordered:
            if empty_start is None:
                empty_start = index
            continue
        if empty_start is not None:
            lines.append(_empty_day_span(empty_start, index - 1))
            lines.append("")
            empty_start = None
        lines.append(DAY_LABELS[index])
        for activity in ordered:
            lines.append(_activity_block(activity.sport_type, activity.name, activity.distance_m, activity.moving_s))
            total_distance_m += activity.distance_m
            total_moving_s += activity.moving_s
        lines.append("")
    if empty_start is not None:
        lines.append(_empty_day_span(empty_start, 6))
        lines.append("")

    this_km = total_distance_m / 1000
    delta = this_km - previous_km
    lines.append("This week")
    lines.append(f"{this_km:.1f} km · {format_clock_duration(total_moving_s)}")
    if abs(delta) < 0.05:
        lines.append("Same distance as last week")
    elif delta > 0:
        lines.append(f"📈 {delta:.1f} km more than last week")
    else:
        lines.append(f"📉 {abs(delta):.1f} km less than last week")
    return "\n".join(lines).rstrip()


def format_shoe_line(name: str, distance_m: float, notification_distance_m: float | None) -> str:
    km = distance_m / 1000
    note = ""
    # Strava stores 0 when the athlete has not set a replacement distance.
    if notification_distance_m and distance_m >= notification_distance_m:
        note = "time to replace"
    elif km >= 800:
        note = "time to replace"
    elif km >= 600:
        note = "consider replacing"
    title = f"⚠️ {name}" if note else name
    stats = f"{km:.1f} km · {note}" if note else f"{km:.1f} km"
    return f"{title}\n{stats}"


def format_recent_line(sport_type: str, name: str, distance_m: float, moving_s: int) -> str:
    return _activity_block(sport_type, name, distance_m, moving_s)


def format_streak(days: int) -> str:
    if days <= 0:
        return "No current run streak."
    return f"{days}-day run streak"


def format_help() -> str:
    return "\n".join(["/shoes", "/week", "/recent", "/streak", "/help", "/cancel"])
