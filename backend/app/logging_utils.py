def fmt_dist(distance_m) -> str:
    if not distance_m:
        return "0.00km"
    return f"{distance_m / 1000:.2f}km"


def fmt_pace(distance_m, moving_time_s) -> str:
    if not distance_m or not moving_time_s:
        return "?:??/km"
    sec_per_km = moving_time_s / (distance_m / 1000)
    return f"{int(sec_per_km // 60)}:{int(sec_per_km % 60):02d}/km"


def fmt_elev(elevation_m) -> str | None:
    if not elevation_m:
        return None
    return f"+{int(elevation_m)}m elev"
