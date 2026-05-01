from datetime import UTC, datetime
from unittest.mock import MagicMock

from app.mcp.formatting import format_activity_detail, format_activity_list
from app.mcp.queries import get_user_activity, list_user_activities
from app.models import StravaActivity, StravaActivityMetric, User


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
