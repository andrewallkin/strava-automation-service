from datetime import UTC, datetime
from unittest.mock import MagicMock

from app.mcp import analysis, server
from app.mcp.formatting import format_activity_detail, format_activity_list
from app.mcp.queries import SKIPPED_MCP_TOOLS, get_user_activity, list_user_activities
from app.models import (
    AthleteProfile,
    AthleteStats,
    Gear,
    StravaActivity,
    StravaActivityLap,
    StravaActivityMetric,
    StravaActivitySplit,
    User,
)


def _activity(activity_id: int, athlete_id: int, deleted: bool = False) -> StravaActivity:
    return StravaActivity(
        activity_id=activity_id,
        athlete_id=athlete_id,
        name=f"Run {activity_id}",
        sport_type="Run",
        start_date_local=datetime(2026, 5, 1, tzinfo=UTC),
        distance_m=5000,
        moving_time_seconds=1500,
        elapsed_time_seconds=1600,
        total_elevation_gain_m=42,
        average_heartrate_bpm=145,
        average_watts=210,
        deleted_at=datetime.now(UTC) if deleted else None,
    )


def test_list_user_activities_returns_bounded_user_rows() -> None:
    user = User(id=1, strava_athlete_id=14460791)
    expected = [_activity(123, 14460791)]
    scalar_result = MagicMock()
    scalar_result.all.return_value = expected
    db = MagicMock()
    db.scalars.return_value = scalar_result

    rows = list_user_activities(db, user, start_date="2026-05-01", end_date="2026-05-02", limit=500)

    assert rows == expected
    stmt = db.scalars.call_args.args[0]
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "strava_activities.athlete_id = 14460791" in compiled
    assert "strava_activities.deleted_at IS NULL" in compiled
    assert "LIMIT 50" in compiled


def test_get_user_activity_scopes_by_athlete_and_excludes_deleted() -> None:
    user = User(id=1, strava_athlete_id=14460791)
    db = MagicMock()
    db.scalar.return_value = _activity(123, 14460791)
    db.get.return_value = StravaActivityMetric(activity_id=123, distance_km=5.0)

    activity, metrics = get_user_activity(db, user, 123)

    assert activity is not None
    assert metrics is not None
    stmt = db.scalar.call_args.args[0]
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "strava_activities.activity_id = 123" in compiled
    assert "strava_activities.athlete_id = 14460791" in compiled
    assert "strava_activities.deleted_at IS NULL" in compiled


def test_mcp_formatters_do_not_return_raw_detail_json() -> None:
    activity = _activity(123, 14460791)
    activity.detail_data = {"secret": "raw payload"}

    list_output = format_activity_list([activity])
    detail_output = format_activity_detail(activity)

    assert "123" in list_output
    assert "Raw Strava detail JSON is intentionally not returned" in detail_output
    assert "raw payload" not in detail_output


def test_catalog_registration_replaces_poc_tools_and_includes_expanded_schema_tools() -> None:
    assert not hasattr(server, "list_activities")
    assert not hasattr(server, "get_activity")
    assert hasattr(server, "search_activities")
    assert hasattr(server, "get_activity_summary")
    assert hasattr(server, "get_athlete_profile")
    assert hasattr(server, "get_shoe_mileage")
    assert hasattr(server, "get_athlete_stats")
    assert SKIPPED_MCP_TOOLS == {}


def test_classify_workout_type_detects_intervals_from_lap_structure(monkeypatch) -> None:
    activity = _activity(123, 14460791)
    laps = [
        StravaActivityLap(lap_index=0, distance_m=1600, average_speed_mps=2.8, moving_time_seconds=570),
        StravaActivityLap(lap_index=1, distance_m=1000, average_speed_mps=3.9, moving_time_seconds=256),
        StravaActivityLap(lap_index=2, distance_m=430, average_speed_mps=2.0, moving_time_seconds=215),
        StravaActivityLap(lap_index=3, distance_m=1000, average_speed_mps=3.95, moving_time_seconds=253),
        StravaActivityLap(lap_index=4, distance_m=430, average_speed_mps=2.0, moving_time_seconds=215),
        StravaActivityLap(lap_index=5, distance_m=1000, average_speed_mps=4.0, moving_time_seconds=250),
        StravaActivityLap(lap_index=6, distance_m=430, average_speed_mps=2.0, moving_time_seconds=215),
    ]
    monkeypatch.setattr(analysis.queries, "require_user_activity", lambda *_args: activity)
    monkeypatch.setattr(analysis.queries, "get_activity_laps", lambda *_args: laps)
    monkeypatch.setattr(analysis.queries, "get_activity_zone_buckets", lambda *_args: [])

    output = analysis.classify_workout_type_text(MagicMock(), User(id=1, strava_athlete_id=14460791), 123)

    assert "type: intervals" in output
    assert "lap_distance_cv" in output


def test_activity_splits_output_flags_fractional_split(monkeypatch) -> None:
    split = StravaActivitySplit(
        split=5,
        split_source="metric",
        distance_m=420,
        moving_time_seconds=130,
        average_speed_mps=3.2,
        average_grade_adjusted_speed_mps=3.3,
        average_heartrate_bpm=150,
        elevation_difference_m=2,
        pace_zone=2,
    )
    monkeypatch.setattr(analysis.queries, "require_user_activity", lambda *_args: _activity(123, 14460791))
    monkeypatch.setattr(analysis.queries, "get_activity_splits", lambda *_args: [split])

    output = analysis.get_activity_splits_text(MagicMock(), User(id=1, strava_athlete_id=14460791), 123)

    assert "split" in output
    assert "fractional" in output
    assert "gap" in output


def test_athlete_profile_uses_cached_profile_and_gear(monkeypatch) -> None:
    profile = AthleteProfile(
        athlete_id=14460791,
        firstname="Andrew",
        lastname="Allkin",
        city="Cape Town",
        country="South Africa",
        sex="M",
        weight_kg=80,
    )
    shoe = Gear(
        strava_gear_id="g1",
        name="ASICS Gel Nimbus 27 #1",
        nickname="Nimbus",
        distance_m=639417,
        retired=False,
        is_default=False,
    )
    monkeypatch.setattr(analysis.queries, "get_athlete_profile", lambda *_args: profile)
    monkeypatch.setattr(analysis.queries, "list_gear_details", lambda *_args, **_kwargs: [shoe])

    output = analysis.get_athlete_profile_text(MagicMock(), User(id=1, strava_athlete_id=14460791))

    assert "Andrew Allkin" in output
    assert "Cape Town" in output
    assert "Nimbus" in output
    assert "639.4 km" in output


def test_athlete_stats_formats_overall_stats(monkeypatch) -> None:
    stats = AthleteStats(
        athlete_id=14460791,
        all_run_count=428,
        all_run_distance_m=3913098.7,
        all_run_moving_time_seconds=1398870,
        all_run_elevation_gain_m=50823.2,
        ytd_run_count=74,
        ytd_run_distance_m=877466,
        ytd_run_moving_time_seconds=306377,
        ytd_run_elevation_gain_m=10257.5,
        biggest_ride_distance_m=203249,
        biggest_climb_elevation_gain_m=1579,
    )
    monkeypatch.setattr(analysis.queries, "get_athlete_stats", lambda *_args: stats)

    output = analysis.get_athlete_stats_text(MagicMock(), User(id=1, strava_athlete_id=14460791))

    assert "all runs" in output
    assert "428" in output
    assert "3,913" not in output
    assert "3913.1 km" in output
    assert "Biggest ride distance" in output
