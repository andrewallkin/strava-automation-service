from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app


def test_oauth_callback_rejects_unauthorized_athlete() -> None:
    """When STRAVA_ALLOWED_ATHLETE_ID is set, reject OAuth from other athletes."""
    with patch("app.services.strava_service.httpx.post") as mock_post:
        mock_post.return_value = MagicMock()
        mock_post.return_value.raise_for_status = MagicMock()
        mock_post.return_value.json.return_value = {
            "athlete": {"id": 999999},
            "access_token": "token",
            "refresh_token": "refresh",
            "expires_at": 1234567890,
        }

        mock_settings = MagicMock()
        mock_settings.strava_allowed_athlete_id = 14460791
        mock_settings.strava_client_id = "client"
        mock_settings.strava_client_secret = "secret"
        mock_settings.strava_scopes = "activity:read,activity:write,profile:read_all"
        mock_settings.public_base_url = "https://example.com"

        with patch("app.services.strava_service.get_settings", return_value=mock_settings):
            client = TestClient(app)
            response = client.get("/api/auth/strava/callback", params={"code": "test_code"})

    assert response.status_code == 403
    assert response.json()["detail"] == "Unauthorized athlete"


def test_strava_webhook_ignores_unauthorized_owner() -> None:
    """When STRAVA_ALLOWED_ATHLETE_ID is set, ignore webhook events from other athletes."""
    mock_settings = MagicMock()
    mock_settings.strava_allowed_athlete_id = 14460791

    with (
        patch("app.routers.strava_webhook.get_settings", return_value=mock_settings),
        patch("app.routers.strava_webhook.log_event"),
    ):
        client = TestClient(app)
        response = client.post(
            "/api/strava/webhook",
            json={
                "object_type": "activity",
                "aspect_type": "create",
                "object_id": 12345,
                "owner_id": 999999,
            },
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ignored", "reason": "unauthorized_owner"}
