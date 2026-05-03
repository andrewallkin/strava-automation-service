from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import httpx

from app.services.strava_service import STRAVA_BASE_URL, StravaRateLimiter, StravaService


def _user() -> MagicMock:
    user = MagicMock()
    user.expires_at = None
    user.refresh_token = None
    user.access_token = "access-token"
    return user


def _service_response(
    status_code: int = 200,
    body: dict | list | None = None,
    headers: dict[str, str] | None = None,
) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.headers = headers or {}
    response.content = b"{}"
    response.json.return_value = body if body is not None else {}
    return response


def test_get_activity_detail_requests_all_efforts() -> None:
    response = _service_response(body={"id": 123})

    with patch("app.services.strava_service.httpx.request", return_value=response) as request:
        result = StravaService().get_activity_detail(MagicMock(), 123, _user())

    assert result == {"id": 123}
    response.raise_for_status.assert_called_once()
    assert request.call_args.args == ("GET", f"{STRAVA_BASE_URL}/api/v3/activities/123")
    assert request.call_args.kwargs["params"] == {"include_all_efforts": "true"}


def test_get_activity_zones_tolerates_unavailable_response() -> None:
    response = _service_response(status_code=403)

    with patch("app.services.strava_service.httpx.request", return_value=response):
        result = StravaService().get_activity_zones(MagicMock(), 123, _user())

    assert result is None
    response.raise_for_status.assert_not_called()


def test_get_athlete_zones_tolerates_unavailable_response() -> None:
    response = _service_response(status_code=403)

    with patch("app.services.strava_service.httpx.request", return_value=response):
        result = StravaService().get_athlete_zones(MagicMock(), _user())

    assert result is None
    response.raise_for_status.assert_not_called()


def test_get_athlete_zones_fetches_zone_snapshot() -> None:
    response = _service_response(body={"heart_rate": {"zones": [{"min": 0, "max": 120}]}})

    with patch("app.services.strava_service.httpx.request", return_value=response) as request:
        result = StravaService().get_athlete_zones(MagicMock(), _user())

    assert result == {"heart_rate": {"zones": [{"min": 0, "max": 120}]}}
    response.raise_for_status.assert_called_once()
    assert request.call_args.args == ("GET", f"{STRAVA_BASE_URL}/api/v3/athlete/zones")


def test_get_athlete_activities_between_paginates_until_short_page() -> None:
    first = _service_response(body=[{"id": i} for i in range(200)])
    second = _service_response(body=[{"id": 201}])

    with patch("app.services.strava_service.httpx.request", side_effect=[first, second]) as request:
        result = StravaService().get_athlete_activities_between(MagicMock(), _user(), 1, 2)

    assert len(result) == 201
    assert request.call_count == 2
    assert request.call_args_list[0].kwargs["params"]["page"] == 1
    assert request.call_args_list[1].kwargs["params"]["page"] == 2


def test_rate_limiter_parses_read_limit_headers() -> None:
    limiter = StravaRateLimiter()
    response = httpx.Response(
        200,
        headers={
            "X-RateLimit-Limit": "200,2000",
            "X-RateLimit-Usage": "12,345",
            "X-ReadRateLimit-Limit": "100,1000",
            "X-ReadRateLimit-Usage": "34,567",
        },
    )

    assert limiter._read_limit(response) == (100, 1000)
    assert limiter._read_usage(response) == (34, 567)


def test_rate_limiter_waits_until_next_15_minute_window() -> None:
    now = datetime(2026, 5, 3, 12, 7, 30, tzinfo=timezone.utc)
    sleeps: list[float] = []
    limiter = StravaRateLimiter(clock=lambda: now, sleeper=sleeps.append)
    response = httpx.Response(
        200,
        headers={
            "X-RateLimit-Limit": "200,2000",
            "X-RateLimit-Usage": "100,10",
        },
    )

    limiter.update_from_response("GET", f"{STRAVA_BASE_URL}/api/v3/athlete", response)
    limiter.wait_before_request("GET", f"{STRAVA_BASE_URL}/api/v3/athlete")

    assert sleeps == [450]


def test_rate_limiter_waits_until_utc_midnight_for_daily_limit() -> None:
    now = datetime(2026, 5, 3, 23, 59, tzinfo=timezone.utc)
    sleeps: list[float] = []
    limiter = StravaRateLimiter(clock=lambda: now, sleeper=sleeps.append)
    response = httpx.Response(
        200,
        headers={
            "X-RateLimit-Limit": "200,2000",
            "X-RateLimit-Usage": "10,1000",
        },
    )

    limiter.update_from_response("GET", f"{STRAVA_BASE_URL}/api/v3/athlete", response)
    limiter.wait_before_request("GET", f"{STRAVA_BASE_URL}/api/v3/athlete")

    assert sleeps == [60]


def test_rate_limited_request_waits_and_retries_once() -> None:
    now = datetime(2026, 5, 3, 12, 7, 30, tzinfo=timezone.utc)
    sleeps: list[float] = []

    def sleep_and_advance(seconds: float) -> None:
        nonlocal now
        sleeps.append(seconds)
        now += timedelta(seconds=seconds)

    limiter = StravaRateLimiter(clock=lambda: now, sleeper=sleep_and_advance)
    first = _service_response(
        status_code=429,
        headers={
            "X-RateLimit-Limit": "200,2000",
            "X-RateLimit-Usage": "100,10",
        },
    )
    second = _service_response(body={"id": 123})

    with (
        patch("app.services.strava_service._STRAVA_RATE_LIMITER", limiter),
        patch("app.services.strava_service.httpx.request", side_effect=[first, second]) as request,
    ):
        result = StravaService().get_activity(MagicMock(), 123, _user())

    assert result == {"id": 123}
    assert request.call_count == 2
    assert sleeps == [450]
