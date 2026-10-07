"""UI routes that read stored activities of every Strava sport_type."""

from datetime import date, datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.deps import require_jwt_user
from app.main import app
from app.models import User
from app.routers import ui_api
from app.services.external_stats import StatActivity

JHB = ZoneInfo("Africa/Johannesburg")


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.pop(require_jwt_user, None)
    app.dependency_overrides.pop(get_db, None)


def _user() -> User:
    return User(id=1, strava_athlete_id=14460791)


def _client_as(user: User) -> TestClient:
    def override_get_db():
        yield MagicMock()

    app.dependency_overrides[require_jwt_user] = lambda: user
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _stat(activity_id: int, sport: str, day: date, moving: int, elapsed: int) -> StatActivity:
    return StatActivity(
        activity_id=activity_id,
        sport_type=sport,
        local_date=day,
        start_local=datetime(day.year, day.month, day.day, 8, tzinfo=JHB),
        distance_m=None,
        moving_time_seconds=moving,
        elevation_gain_m=None,
        average_cadence_spm=None,
        has_heartrate=False,
        hr_zones=(0, 0, 0, 0, 0),
        description=None,
        elapsed_time_seconds=elapsed,
    )


def test_new_ui_routes_require_login() -> None:
    client = TestClient(app)
    assert client.get("/api/ui/stored-activities").status_code == 401
    assert client.get("/api/ui/activity-type-summary").status_code == 401


def test_stored_activities_lists_newest_first_without_filters(monkeypatch) -> None:
    calls: dict = {}

    def fake_list(db, user, **kwargs):
        calls.update(kwargs)
        calls["user"] = user
        return {
            "data": [{"id": "19714619129", "sportType": "Padel"}],
            "pagination": {"page": 2, "perPage": 5, "total": 6, "totalPages": 2, "nextPage": None},
        }

    monkeypatch.setattr(ui_api, "list_activities", fake_list)
    user = _user()
    response = _client_as(user).get("/api/ui/stored-activities?page=2&perPage=5")

    assert response.status_code == 200
    assert response.json()["data"][0]["sportType"] == "Padel"
    assert calls["user"] is user
    assert calls["page"] == 2
    assert calls["per_page"] == 5
    assert calls["sort"] == "start_date_desc"
    assert calls["sport"] is None
    assert calls["type_group_name"] is None


def test_stored_activities_defaults_to_first_page_of_15(monkeypatch) -> None:
    calls: dict = {}
    monkeypatch.setattr(
        ui_api,
        "list_activities",
        lambda db, user, **kwargs: calls.update(kwargs) or {"data": [], "pagination": {}},
    )
    assert _client_as(_user()).get("/api/ui/stored-activities").status_code == 200
    assert calls["page"] == 1
    assert calls["per_page"] == 15


def test_stored_activities_rejects_out_of_range_paging(monkeypatch) -> None:
    monkeypatch.setattr(ui_api, "list_activities", lambda *args, **kwargs: {"data": [], "pagination": {}})
    client = _client_as(_user())
    assert client.get("/api/ui/stored-activities?perPage=51").status_code == 422
    assert client.get("/api/ui/stored-activities?perPage=0").status_code == 422
    assert client.get("/api/ui/stored-activities?page=0").status_code == 422


def test_activity_type_summary_splits_this_week_and_last_week(monkeypatch) -> None:
    monkeypatch.setattr(ui_api, "local_today", lambda: date(2026, 10, 7))
    loaded: dict = {}

    def fake_between(db, user, start, end):
        loaded["range"] = (start, end)
        return [
            _stat(1, "Padel", date(2026, 10, 6), 4285, 4968),
            _stat(2, "Walk", date(2026, 10, 5), 3004, 3020),
            _stat(3, "Golf", date(2026, 9, 30), 5823, 10775),
        ]

    monkeypatch.setattr(ui_api, "stat_activities_between", fake_between)
    response = _client_as(_user()).get("/api/ui/activity-type-summary")

    assert response.status_code == 200
    body = response.json()
    assert loaded["range"] == (date(2026, 9, 28), date(2026, 10, 11))
    assert body["thisWeek"]["start"] == "2026-10-05"
    assert body["thisWeek"]["end"] == "2026-10-11"
    assert set(body["thisWeek"]["bySportType"]) == {"Padel", "Walk"}
    assert body["thisWeek"]["bySportType"]["Padel"]["elapsedTimeSec"] == 4968
    assert body["lastWeek"]["start"] == "2026-09-28"
    assert body["lastWeek"]["end"] == "2026-10-04"
    assert body["lastWeek"]["bySportType"] == {
        "Golf": {
            "activityCount": 1,
            "distanceM": 0.0,
            "movingTimeSec": 5823,
            "elapsedTimeSec": 10775,
            "elevationGainM": 0.0,
            "days": ["2026-09-30"],
        }
    }


def test_activity_type_summary_is_empty_without_activities(monkeypatch) -> None:
    monkeypatch.setattr(ui_api, "local_today", lambda: date(2026, 10, 7))
    monkeypatch.setattr(ui_api, "stat_activities_between", lambda *args, **kwargs: [])
    body = _client_as(_user()).get("/api/ui/activity-type-summary").json()
    assert body["thisWeek"]["bySportType"] == {}
    assert body["lastWeek"]["bySportType"] == {}
