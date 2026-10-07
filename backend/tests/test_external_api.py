"""External read API: key auth, activity scope, and weekly coaching flags."""

from datetime import date, datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import bcrypt
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.mcp.queries import get_user_activity
from app.models import StravaActivity, User
from app.services.external_activities import activity_summary, stat_activities_between
from app.services.external_api_key_service import (
    assign_external_api_key,
    authenticate_external_api_key,
    revoke_external_api_key,
)
from app.services.external_stats import StatActivity, consistency, rollup, summarize_window

JHB = ZoneInfo("Africa/Johannesburg")


def _user() -> User:
    return User(id=1, strava_athlete_id=14460791)


def _assign(user: User) -> str:
    db = MagicMock()
    return assign_external_api_key(db, user)


def test_external_api_key_stores_hash_not_plaintext() -> None:
    user = _user()
    raw = _assign(user)

    assert user.external_api_key_hash is not None
    assert raw not in user.external_api_key_hash
    assert user.external_api_key_prefix == raw[:12]
    assert bcrypt.checkpw(raw.encode(), user.external_api_key_hash.encode())


def test_second_generate_invalidates_the_first_key() -> None:
    user = _user()
    first = _assign(user)
    second = _assign(user)

    assert not bcrypt.checkpw(first.encode(), user.external_api_key_hash.encode())
    assert bcrypt.checkpw(second.encode(), user.external_api_key_hash.encode())
    assert user.external_api_key_prefix == second[:12]


def test_revoke_clears_key_material() -> None:
    user = _user()
    _assign(user)
    db = MagicMock()
    revoke_external_api_key(db, user)

    assert user.external_api_key_prefix is None
    assert user.external_api_key_hash is None
    assert user.external_api_key_created_at is None
    db.commit.assert_called_once()


def test_authenticate_rejects_mcp_keys_and_accepts_external_keys() -> None:
    user = _user()
    raw = _assign(user)
    db = MagicMock()
    db.scalar.return_value = user

    assert authenticate_external_api_key(db, raw) is user
    assert authenticate_external_api_key(db, "sva_mcp_" + "x" * 20) is None
    assert authenticate_external_api_key(db, "not-a-key") is None


def test_external_routes_reject_missing_key_and_session_cookie() -> None:
    client = TestClient(app)
    missing = client.get("/api/external/athlete")
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "unauthorized"

    client.cookies.set("session", "not-an-external-key")
    cookie = client.get("/api/external/athlete")
    assert cookie.status_code == 401

    mcp = client.get("/api/external/athlete", headers={"Authorization": "Bearer sva_mcp_" + "x" * 24})
    assert mcp.status_code == 401


def test_activity_lookup_is_scoped_to_the_athlete_and_excludes_deleted() -> None:
    user = _user()
    db = MagicMock()
    db.scalar.return_value = None

    assert get_user_activity(db, user, 555) == (None, None)
    compiled = str(db.scalar.call_args.args[0].compile(compile_kwargs={"literal_binds": True}))
    assert "strava_activities.athlete_id = 14460791" in compiled
    assert "strava_activities.activity_id = 555" in compiled
    assert "deleted_at IS NULL" in compiled


def test_missing_activity_returns_404_on_detail_and_child_routes() -> None:
    user = _user()
    raw = _assign(user)
    db = MagicMock()
    db.scalar.side_effect = lambda *_args, **_kwargs: user if db.scalar.call_count == 1 else None

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        headers = {"Authorization": f"Bearer {raw}"}
        for path in (
            "/api/external/activities/999",
            "/api/external/activities/999/laps",
            "/api/external/activities/999/splits",
            "/api/external/activities/999/zones",
            "/api/external/activities/999/best-efforts",
        ):
            db.scalar.side_effect = lambda *_args, **_kwargs: user if db.scalar.call_count == 1 else None
            db.scalar.call_count = 0
            response = client.get(path, headers=headers)
            assert response.status_code == 404, path
            assert response.json()["error"]["code"] == "not_found"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_activity_summary_omits_temperature_when_detail_has_none() -> None:
    activity = StravaActivity(activity_id=1, athlete_id=1, sport_type="Run", detail_data={"name": "easy"})
    assert activity_summary(activity)["averageTempC"] is None


def _stat(
    activity_id: int,
    sport: str,
    day: int,
    hour: int,
    distance: float | None,
    hr_zones: tuple[int, int, int, int, int] = (0, 0, 0, 0, 0),
    has_heartrate: bool = True,
    description: str | None = None,
) -> StatActivity:
    start = datetime(2026, 10, day, hour, tzinfo=JHB)
    return StatActivity(
        activity_id=activity_id,
        sport_type=sport,
        local_date=start.date(),
        start_local=start,
        distance_m=distance,
        moving_time_seconds=1800,
        elevation_gain_m=10,
        average_cadence_spm=170,
        has_heartrate=has_heartrate,
        hr_zones=hr_zones,
        description=description,
    )


def test_weekly_flags_volume_jump_and_run_after_legs() -> None:
    previous = summarize_window(
        [_stat(1, "Run", 5, 7, 10000)],
        start=date(2026, 10, 5),
        end=date(2026, 10, 11),
        previous=None,
    )
    current_rows = [
        _stat(2, "Run", 12, 8, 12000),
        _stat(3, "WeightTraining", 12, 6, None),
    ]
    current = summarize_window(
        current_rows,
        start=date(2026, 10, 12),
        end=date(2026, 10, 18),
        previous=previous,
    )
    assert "volume_jump_high" in current["flags"]
    assert "run_after_legs" in current["flags"]
    assert current["strength"]["sameDayAsRun"][0]["runFirst"] is False


def test_rollup_flags_the_first_returned_week_against_the_week_before() -> None:
    activities = [
        _stat(1, "Run", 5, 7, 20000),
        _stat(2, "Run", 12, 8, 6000),
        _stat(3, "Run", 13, 8, 17000),
    ]
    weeks = rollup(activities, [(date(2026, 10, 12), date(2026, 10, 18))], "week")
    assert "volume_jump_high" in weeks[0]["flags"]
    assert "long_run_jump_high" not in weeks[0]["flags"]
    assert weeks[0]["weekOverWeekDistancePct"] == 15.0


def test_injury_keyword_it_does_not_match_inside_with() -> None:
    today = date(2026, 10, 6)
    rows = [_stat(1, "Run", 6, 7, 5000, description="easy run with friends")]
    assert consistency(rows, today)["injuryFlagKeywordsInNotes"] == []
    flagged = [_stat(1, "Run", 6, 7, 5000, description="IT band sore")]
    assert consistency(flagged, today)["injuryFlagKeywordsInNotes"] == ["IT"]


WEEK = (date(2026, 10, 5), date(2026, 10, 11))


def _typed(
    activity_id: int,
    sport: str | None,
    day: int,
    *,
    distance: float | None = None,
    moving: int | None = 1800,
    elapsed: int | None = None,
    elevation: float | None = 0.0,
) -> StatActivity:
    start = datetime(2026, 10, day, 8, tzinfo=JHB)
    return StatActivity(
        activity_id=activity_id,
        sport_type=sport,
        local_date=start.date(),
        start_local=start,
        distance_m=distance,
        moving_time_seconds=moving,
        elevation_gain_m=elevation,
        average_cadence_spm=None,
        has_heartrate=True,
        hr_zones=(0, 0, 0, 0, 0),
        description=None,
        elapsed_time_seconds=elapsed,
    )


def test_by_sport_type_keys_are_exact_strava_sport_types() -> None:
    rows = [
        _typed(1, "Run", 5, distance=8200, moving=2690, elapsed=2730, elevation=72),
        _typed(2, "Run", 7, distance=10100, moving=3150, elapsed=3205, elevation=92),
        _typed(3, "Walk", 5, distance=4349.7, moving=3004, elapsed=3020, elevation=231),
        _typed(4, "Golf", 6, distance=5708.6, moving=5823, elapsed=10775, elevation=88),
        _typed(5, "Padel", 6, distance=2508, moving=4285, elapsed=4968, elevation=0),
        _typed(6, "Workout", 7, distance=0, moving=2763, elapsed=2763, elevation=0),
        _typed(7, "WeightTraining", 6, distance=None, moving=3300, elapsed=3300, elevation=None),
    ]
    result = summarize_window(rows, *WEEK, previous=None)["bySportType"]

    assert set(result) == {"Run", "Walk", "Golf", "Padel", "Workout", "WeightTraining"}
    assert result["Run"] == {
        "activityCount": 2,
        "distanceM": 18300.0,
        "movingTimeSec": 5840,
        "elapsedTimeSec": 5935,
        "elevationGainM": 164.0,
        "days": ["2026-10-05", "2026-10-07"],
    }
    assert result["Golf"] == {
        "activityCount": 1,
        "distanceM": 5708.6,
        "movingTimeSec": 5823,
        "elapsedTimeSec": 10775,
        "elevationGainM": 88.0,
        "days": ["2026-10-06"],
    }
    assert result["WeightTraining"] == {
        "activityCount": 1,
        "distanceM": 0.0,
        "movingTimeSec": 3300,
        "elapsedTimeSec": 3300,
        "elevationGainM": 0.0,
        "days": ["2026-10-06"],
    }


def test_by_sport_type_counts_missing_sport_type_as_unknown_and_empty_window_is_empty() -> None:
    rows = [_typed(1, None, 5, moving=None, elapsed=None)]
    assert summarize_window(rows, *WEEK, previous=None)["bySportType"] == {
        "Unknown": {
            "activityCount": 1,
            "distanceM": 0.0,
            "movingTimeSec": 0,
            "elapsedTimeSec": 0,
            "elevationGainM": 0.0,
            "days": ["2026-10-05"],
        }
    }
    assert summarize_window([], *WEEK, previous=None)["bySportType"] == {}


def test_by_sport_type_excludes_activities_outside_the_window() -> None:
    rows = [_typed(1, "Walk", 4), _typed(2, "Walk", 12)]
    assert summarize_window(rows, *WEEK, previous=None)["bySportType"] == {}


def test_existing_groups_are_unchanged_by_the_sport_type_breakdown() -> None:
    rows = [
        _typed(1, "Run", 5, distance=5000),
        _typed(2, "Workout", 5),
        _typed(3, "WeightTraining", 6),
        _typed(4, "Padel", 6),
        _typed(5, "Walk", 7),
    ]
    window = summarize_window(rows, *WEEK, previous=None)
    assert window["run"]["activityCount"] == 1
    assert window["strength"]["activityCount"] == 2
    assert window["other"] == {"activityCount": 2}


def test_consistency_reports_activity_counts_by_sport_type() -> None:
    rows = [
        _typed(1, "Run", 5, distance=5000),
        _typed(2, "Run", 6, distance=5000),
        _typed(3, "Padel", 6),
        _typed(4, "Golf", 7),
    ]
    assert consistency(rows, date(2026, 10, 7))["activitiesBySportType28d"] == {"Golf": 1, "Padel": 1, "Run": 2}


def test_stat_activities_use_sport_type_not_type_and_carry_elapsed_time() -> None:
    padel = StravaActivity(
        activity_id=19714619129,
        athlete_id=14460791,
        activity_type="Workout",
        sport_type="Padel",
        local_date=date(2026, 8, 12),
        start_date_local=datetime(2026, 8, 12, 18, 34, 24, tzinfo=JHB),
        distance_m=2508,
        moving_time_seconds=4285,
        elapsed_time_seconds=4968,
        total_elevation_gain_m=0,
        has_heartrate=True,
    )
    db = MagicMock()
    db.scalars.return_value.all.side_effect = [[padel], []]

    rows = stat_activities_between(db, _user(), date(2026, 8, 10), date(2026, 8, 16))

    assert len(rows) == 1
    assert rows[0].sport_type == "Padel"
    assert rows[0].elapsed_time_seconds == 4968
    window = summarize_window(rows, date(2026, 8, 10), date(2026, 8, 16), previous=None)
    assert window["bySportType"]["Padel"]["activityCount"] == 1
