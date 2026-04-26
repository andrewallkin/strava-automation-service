from unittest.mock import MagicMock, patch

from app.services.strava_service import StravaService


def _user() -> MagicMock:
    user = MagicMock()
    user.expires_at = None
    user.refresh_token = None
    user.access_token = "access-token"
    return user


def test_get_activity_detail_requests_all_efforts() -> None:
    response = MagicMock()
    response.json.return_value = {"id": 123}

    with patch("app.services.strava_service.httpx.get", return_value=response) as mock_get:
        result = StravaService().get_activity_detail(MagicMock(), 123, _user())

    assert result == {"id": 123}
    response.raise_for_status.assert_called_once()
    assert mock_get.call_args.kwargs["params"] == {"include_all_efforts": "true"}


def test_get_activity_zones_tolerates_unavailable_response() -> None:
    response = MagicMock()
    response.status_code = 403

    with patch("app.services.strava_service.httpx.get", return_value=response):
        result = StravaService().get_activity_zones(MagicMock(), 123, _user())

    assert result is None
    response.raise_for_status.assert_not_called()


def test_get_athlete_activities_between_paginates_until_short_page() -> None:
    first = MagicMock()
    first.json.return_value = [{"id": i} for i in range(200)]
    second = MagicMock()
    second.json.return_value = [{"id": 201}]

    with patch("app.services.strava_service.httpx.get", side_effect=[first, second]) as mock_get:
        result = StravaService().get_athlete_activities_between(MagicMock(), _user(), 1, 2)

    assert len(result) == 201
    assert mock_get.call_count == 2
    assert mock_get.call_args_list[0].kwargs["params"]["page"] == 1
    assert mock_get.call_args_list[1].kwargs["params"]["page"] == 2
