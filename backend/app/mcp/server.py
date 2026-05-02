from __future__ import annotations

import logging
from collections.abc import Callable

from fastmcp import FastMCP
from fastmcp.server.auth.providers.debug import DebugTokenVerifier

from app.config import get_settings
from app.db import SessionLocal
from app.mcp import analysis
from app.mcp.auth import McpAuthError, require_mcp_user
from app.services.mcp_api_key_service import is_valid_mcp_api_key

log = logging.getLogger("mcp")
mcp = FastMCP(
    "strava-automation-service",
    auth=DebugTokenVerifier(
        validate=is_valid_mcp_api_key,
        client_id="strava-automation-service",
        scopes=["activities:read"],
    ),
)


def _run_tool(operation: Callable[..., str], **kwargs: object) -> str:
    try:
        user = require_mcp_user()
        with SessionLocal() as db:
            return operation(db, user, **kwargs)
    except McpAuthError as exc:
        return f"Authentication failed: {exc}"
    except ValueError as exc:
        return f"Invalid request: {exc}"
    except Exception:
        log.exception("MCP tool failed | tool=%s", getattr(operation, "__name__", "unknown"))
        return "Unable to complete the request due to an internal service error."


@mcp.tool()
def get_athlete_profile() -> str:
    """Return cached athlete profile context and shoe summary."""
    return _run_tool(analysis.get_athlete_profile_text)


@mcp.tool()
def get_heart_rate_zones() -> str:
    """Return current cached athlete HR zone definitions."""
    return _run_tool(analysis.get_heart_rate_zones_text)


@mcp.tool()
def search_activities(
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
    """Filter locally ingested run activities by common criteria."""
    return _run_tool(
        analysis.search_activities_text,
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
    )


@mcp.tool()
def list_recent_runs(n: int = 10) -> str:
    """Return the most recent locally ingested runs."""
    return _run_tool(analysis.list_recent_runs_text, n=n)


@mcp.tool()
def find_activity_by_date(date: str, sport_type: str | None = None) -> str:
    """Resolve a date, today, or yesterday to activity IDs."""
    return _run_tool(analysis.find_activity_by_date_text, date_value=date, sport_type=sport_type)


@mcp.tool()
def find_similar_runs(
    reference_activity_id: int,
    lookback_days: int = 90,
    distance_tolerance_pct: float = 15,
    elev_tolerance_pct: float = 25,
    elev_tolerance_abs_m: float = 50,
    limit: int = 10,
) -> str:
    """Find historical runs comparable to a reference run."""
    return _run_tool(
        analysis.find_similar_runs_text,
        reference_activity_id=reference_activity_id,
        lookback_days=lookback_days,
        distance_tolerance_pct=distance_tolerance_pct,
        elev_tolerance_pct=elev_tolerance_pct,
        elev_tolerance_abs_m=elev_tolerance_abs_m,
        limit=limit,
    )


@mcp.tool()
def get_activity_summary(activity_id: int) -> str:
    """Return a compact one-page activity summary."""
    return _run_tool(analysis.get_activity_summary_text, activity_id=activity_id)


@mcp.tool()
def get_activity_full_details(activity_id: int) -> str:
    """Return bounded full details for one activity."""
    return _run_tool(analysis.get_activity_full_details_text, activity_id=activity_id)


@mcp.tool()
def classify_workout_type(activity_id: int) -> str:
    """Heuristically classify a run workout type."""
    return _run_tool(analysis.classify_workout_type_text, activity_id=activity_id)


@mcp.tool()
def get_activity_laps(activity_id: int) -> str:
    """Return the stored lap table for an activity."""
    return _run_tool(analysis.get_activity_laps_text, activity_id=activity_id)


@mcp.tool()
def analyze_intervals(activity_id: int) -> str:
    """Analyze interval structure, consistency, recovery, and fade."""
    return _run_tool(analysis.analyze_intervals_text, activity_id=activity_id)


@mcp.tool()
def compare_laps_within_activity(activity_id: int) -> str:
    """Compare lap deltas across one activity."""
    return _run_tool(analysis.compare_laps_within_activity_text, activity_id=activity_id)


@mcp.tool()
def get_warmup_cooldown_quality(activity_id: int) -> str:
    """Assess warmup and cooldown quality from lap data."""
    return _run_tool(analysis.get_warmup_cooldown_quality_text, activity_id=activity_id)


@mcp.tool()
def get_activity_splits(activity_id: int, unit: str = "metric") -> str:
    """Return per-km or per-mile splits."""
    return _run_tool(analysis.get_activity_splits_text, activity_id=activity_id, unit=unit)


@mcp.tool()
def analyze_pacing(activity_id: int, unit: str = "metric") -> str:
    """Analyze steady-run pacing structure."""
    return _run_tool(analysis.analyze_pacing_text, activity_id=activity_id, unit=unit)


@mcp.tool()
def analyze_grade_adjusted_pace(activity_id: int) -> str:
    """Compare actual pace to Strava grade-adjusted pace."""
    return _run_tool(analysis.analyze_grade_adjusted_pace_text, activity_id=activity_id)


@mcp.tool()
def get_activity_hr_zone_distribution(activity_id: int) -> str:
    """Return time-in-HR-zone for one activity."""
    return _run_tool(analysis.get_activity_hr_zone_distribution_text, activity_id=activity_id)


@mcp.tool()
def analyze_hr_decoupling(activity_id: int) -> str:
    """Estimate HR decoupling from split-level pace and HR."""
    return _run_tool(analysis.analyze_hr_decoupling_text, activity_id=activity_id)


@mcp.tool()
def get_period_hr_zone_distribution(start_date: str, end_date: str, sport_type: str | None = None) -> str:
    """Aggregate HR-zone distribution over a date range."""
    return _run_tool(
        analysis.get_period_hr_zone_distribution_text,
        start_date=start_date,
        end_date=end_date,
        sport_type=sport_type,
    )


@mcp.tool()
def validate_hr_zones(lookback_days: int = 60) -> str:
    """Diagnose whether cached HR zones look calibrated."""
    return _run_tool(analysis.validate_hr_zones_text, lookback_days=lookback_days)


@mcp.tool()
def analyze_cadence(activity_id: int) -> str:
    """Analyze per-lap cadence and baseline comparison."""
    return _run_tool(analysis.analyze_cadence_text, activity_id=activity_id)


@mcp.tool()
def get_cadence_trend(
    start_date: str | None = None,
    end_date: str | None = None,
    lookback_days: int | None = None,
) -> str:
    """Return average cadence trend over time."""
    return _run_tool(
        analysis.get_cadence_trend_text,
        start_date=start_date,
        end_date=end_date,
        lookback_days=lookback_days,
    )


@mcp.tool()
def get_elevation_profile_summary(activity_id: int) -> str:
    """Return terrain context without map data."""
    return _run_tool(analysis.get_elevation_profile_summary_text, activity_id=activity_id)


@mcp.tool()
def get_activity_best_efforts(activity_id: int) -> str:
    """Return best efforts stored for one activity."""
    return _run_tool(analysis.get_activity_best_efforts_text, activity_id=activity_id)


@mcp.tool()
def track_best_effort_progression(effort_name: str, lookback_days: int = 365, limit: int = 50) -> str:
    """Track benchmark best-effort progression over time."""
    return _run_tool(
        analysis.track_best_effort_progression_text,
        effort_name=effort_name,
        lookback_days=lookback_days,
        limit=limit,
    )


@mcp.tool()
def find_pr_activities(lookback_days: int = 365) -> str:
    """Find activities with stored PR best efforts."""
    return _run_tool(analysis.find_pr_activities_text, lookback_days=lookback_days)


@mcp.tool()
def get_weekly_summary(weeks: int = 4, week_start: str = "monday") -> str:
    """Return per-week training rollups."""
    return _run_tool(analysis.get_weekly_summary_text, weeks=weeks, week_start=week_start)


@mcp.tool()
def get_monthly_summary(months: int = 6) -> str:
    """Return per-calendar-month training rollups."""
    return _run_tool(analysis.get_monthly_summary_text, months=months)


@mcp.tool()
def get_period_summary(start_date: str, end_date: str, sport_type: str | None = None) -> str:
    """Return one custom date-range rollup."""
    return _run_tool(analysis.get_period_summary_text, start_date=start_date, end_date=end_date, sport_type=sport_type)


@mcp.tool()
def get_volume_trend(weeks: int = 12) -> str:
    """Return weekly volume trend with ramp flags."""
    return _run_tool(analysis.get_volume_trend_text, weeks=weeks)


@mcp.tool()
def get_intensity_distribution(start_date: str, end_date: str) -> str:
    """Classify period intensity distribution from HR zones."""
    return _run_tool(analysis.get_intensity_distribution_text, start_date=start_date, end_date=end_date)


@mcp.tool()
def get_long_run_progression(weeks: int = 12) -> str:
    """Return longest-run-per-week progression."""
    return _run_tool(analysis.get_long_run_progression_text, weeks=weeks)


@mcp.tool()
def get_pace_at_distance_progression(
    min_distance_km: float,
    max_distance_km: float,
    lookback_days: int = 180,
) -> str:
    """Return pace trend within a distance band."""
    return _run_tool(
        analysis.get_pace_at_distance_progression_text,
        min_distance_km=min_distance_km,
        max_distance_km=max_distance_km,
        lookback_days=lookback_days,
    )


@mcp.tool()
def compare_activities(activity_id_a: int, activity_id_b: int) -> str:
    """Compare two activities side-by-side."""
    return _run_tool(analysis.compare_activities_text, activity_id_a=activity_id_a, activity_id_b=activity_id_b)


@mcp.tool()
def compare_periods(
    period_a_start: str,
    period_a_end: str,
    period_b_start: str,
    period_b_end: str,
) -> str:
    """Compare two date ranges."""
    return _run_tool(
        analysis.compare_periods_text,
        period_a_start=period_a_start,
        period_a_end=period_a_end,
        period_b_start=period_b_start,
        period_b_end=period_b_end,
    )


@mcp.tool()
def compare_to_similar_recent_runs(activity_id: int, lookback_days: int = 90, n_similar: int = 5) -> str:
    """Compare one activity to similar recent runs."""
    return _run_tool(
        analysis.compare_to_similar_recent_runs_text,
        activity_id=activity_id,
        lookback_days=lookback_days,
        n_similar=n_similar,
    )


@mcp.tool()
def get_recovery_status(as_of_date: str | None = None) -> str:
    """Return a simple recovery status snapshot."""
    return _run_tool(analysis.get_recovery_status_text, as_of_date=as_of_date)


@mcp.tool()
def compute_acute_chronic_ratio(as_of_date: str | None = None, metric: str = "distance") -> str:
    """Compute acute:chronic workload ratio."""
    return _run_tool(analysis.compute_acute_chronic_ratio_text, as_of_date=as_of_date, metric=metric)


@mcp.tool()
def detect_training_red_flags(lookback_weeks: int = 4) -> str:
    """Surface training red flags from recent stored data."""
    return _run_tool(analysis.detect_training_red_flags_text, lookback_weeks=lookback_weeks)


@mcp.tool()
def get_shoe_mileage(include_retired: bool = False) -> str:
    """Return per-shoe usage, mileage, and replacement flags."""
    return _run_tool(analysis.get_shoe_mileage_text, include_retired=include_retired)


@mcp.tool()
def get_athlete_stats() -> str:
    """Return cached overall Strava athlete stats."""
    return _run_tool(analysis.get_athlete_stats_text)


@mcp.tool()
def check_data_availability(
    activity_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    """Report stored data availability for one activity or date range."""
    return _run_tool(
        analysis.check_data_availability_text,
        activity_id=activity_id,
        start_date=start_date,
        end_date=end_date,
    )


if __name__ == "__main__":
    settings = get_settings()
    mcp.run(transport="sse", host=settings.app_host, port=settings.app_port)
