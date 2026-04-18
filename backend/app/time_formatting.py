"""Format moving-time durations for display (seconds since activity start)."""


def format_moving_time_s(seconds: int | float) -> str:
    """Human-readable duration, e.g. 1h 24m 34s, 45m 30s, 34s, 0s."""
    s = max(0, int(seconds))
    h, r = divmod(s, 3600)
    m, sec = divmod(r, 60)
    parts: list[str] = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    if sec:
        parts.append(f"{sec}s")
    if not parts:
        parts.append("0s")
    return " ".join(parts)
