from __future__ import annotations

from typing import Any

from agents import HostedMCPTool

from .settings import get_planner_settings

# Mirrors backend coach Strava MCP allowlist (standalone copy; do not import backend).
ALLOWED_MCP_TOOLS = [
    "get_athlete_profile",
    "get_heart_rate_zones",
    "get_current_date",
    "search_activities",
    "list_recent_runs",
    "find_activity_by_date",
    "find_similar_runs",
    "get_activity_summary",
    "get_activity_full_details",
    "classify_workout_type",
    "get_activity_laps",
    "analyze_intervals",
    "compare_laps_within_activity",
    "get_warmup_cooldown_quality",
    "get_activity_splits",
    "analyze_pacing",
    "analyze_grade_adjusted_pace",
    "get_activity_hr_zone_distribution",
    "analyze_hr_decoupling",
    "get_period_hr_zone_distribution",
    "validate_hr_zones",
    "analyze_cadence",
    "get_cadence_trend",
    "get_elevation_profile_summary",
    "get_activity_best_efforts",
    "track_best_effort_progression",
    "find_pr_activities",
    "get_weekly_summary",
    "get_monthly_summary",
    "get_period_summary",
    "get_volume_trend",
    "get_intensity_distribution",
    "get_long_run_progression",
    "get_pace_at_distance_progression",
    "compare_activities",
    "compare_periods",
    "compare_to_similar_recent_runs",
    "get_recovery_status",
    "compute_acute_chronic_ratio",
    "detect_training_red_flags",
    "get_shoe_mileage",
    "get_athlete_stats",
    "check_data_availability",
]


def make_strava_mcp_tool() -> HostedMCPTool:
    settings = get_planner_settings()
    if not settings.mcp_server_url or not settings.strava_mcp_bearer:
        raise RuntimeError(
            "Missing MCP_SERVER_URL or STRAVA_MCP_BEARER in the environment or .env; Strava analysis cannot run."
        )

    tool_config: dict[str, Any] = {
        "type": "mcp",
        "server_label": "Strava_MCP",
        "server_url": settings.mcp_server_url,
        "server_description": "Strava MCP Server",
        "headers": {"Authorization": f"Bearer {settings.strava_mcp_bearer}"},
        "allowed_tools": ALLOWED_MCP_TOOLS,
        "require_approval": "never",
    }
    return HostedMCPTool(tool_config=tool_config)
