from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.services.strava_service import StravaService


def _user() -> MagicMock:
    user = MagicMock()
    user.expires_at = None
    user.refresh_token = None
    user.access_token = "access-token"
    return user


def _json_response(status_code: int, body: dict) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.headers = {
        "content-type": "application/json",
        "x-ratelimit-usage": "1,100",
    }
    response.content = b"{}"
    response.json.return_value = body
    response.request.url = "https://www.strava.com/api/v3/athlete"
    return response


def test_explore_api_normalizes_endpoint_and_merges_query_params() -> None:
    response = _json_response(200, {"id": 123})

    with patch("app.services.strava_service.httpx.request", return_value=response) as request:
        result = StravaService().explore_api(
            MagicMock(),
            _user(),
            method="get",
            endpoint="/athlete/activities?per_page=5",
            params={"page": 1},
        )

    assert result["status_code"] == 200
    assert result["endpoint"] == "/api/v3/athlete/activities"
    assert result["body"] == {"id": 123}
    assert result["headers"] == {
        "content-type": "application/json",
        "x-ratelimit-usage": "1,100",
    }
    assert request.call_args.args == ("GET", "https://www.strava.com/api/v3/athlete/activities")
    assert request.call_args.kwargs["params"] == {"per_page": "5", "page": 1}
    assert request.call_args.kwargs["headers"]["Authorization"] == "Bearer access-token"


def test_explore_api_accepts_existing_api_v3_path() -> None:
    response = _json_response(200, {"ok": True})

    with patch("app.services.strava_service.httpx.request", return_value=response) as request:
        result = StravaService().explore_api(
            MagicMock(),
            _user(),
            method="GET",
            endpoint="/api/v3/athlete",
        )

    assert result["endpoint"] == "/api/v3/athlete"
    assert request.call_args.args == ("GET", "https://www.strava.com/api/v3/athlete")


def test_explore_api_rejects_full_urls() -> None:
    try:
        StravaService().explore_api(
            MagicMock(),
            _user(),
            method="GET",
            endpoint="https://www.strava.com/api/v3/athlete",
        )
    except HTTPException as exc:
        assert exc.status_code == 400
        assert exc.detail == "Use a Strava API path, not a full URL"
    else:
        raise AssertionError("Expected HTTPException")


def test_explore_api_returns_strava_error_response_body() -> None:
    response = _json_response(404, {"message": "Record Not Found"})

    with patch("app.services.strava_service.httpx.request", return_value=response):
        result = StravaService().explore_api(
            MagicMock(),
            _user(),
            method="GET",
            endpoint="/activities/1",
        )

    assert result["status_code"] == 404
    assert result["body"] == {"message": "Record Not Found"}
