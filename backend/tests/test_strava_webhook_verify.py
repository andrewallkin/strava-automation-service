from fastapi.testclient import TestClient

from app.main import app


def test_strava_webhook_verify_fail_without_token() -> None:
    client = TestClient(app)
    response = client.get(
        "/api/strava/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": "bad", "hub.challenge": "123"},
    )
    assert response.status_code == 403


def test_strava_webhook_create_queues_existing_processor() -> None:
    client = TestClient(app)

    from unittest.mock import MagicMock, patch

    mock_settings = MagicMock()
    mock_settings.strava_allowed_athlete_id = 0

    with (
        patch("app.routers.strava_webhook.get_settings", return_value=mock_settings),
        patch("app.routers.strava_webhook.log_event"),
        patch("app.routers.strava_webhook.process_activity") as mock_process,
        patch("app.routers.strava_webhook.ingest_activity_event") as mock_ingest,
    ):
        response = client.post(
            "/api/strava/webhook",
            json={
                "object_type": "activity",
                "aspect_type": "create",
                "object_id": 12345,
                "owner_id": 67890,
            },
        )

    assert response.status_code == 200
    assert response.json() == {"status": "queued", "activity_id": 12345}
    mock_process.assert_called_once_with(12345, 67890, 0)
    mock_ingest.assert_called_once_with(12345, 67890, "create", "webhook")


def test_strava_webhook_non_create_does_not_queue_existing_processor() -> None:
    client = TestClient(app)

    from unittest.mock import patch

    with (
        patch("app.routers.strava_webhook.log_event"),
        patch("app.routers.strava_webhook.process_activity") as mock_process,
        patch("app.routers.strava_webhook.ingest_activity_event") as mock_ingest,
    ):
        response = client.post(
            "/api/strava/webhook",
            json={
                "object_type": "activity",
                "aspect_type": "update",
                "object_id": 12345,
                "owner_id": 67890,
            },
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ignored", "reason": "non-create event"}
    mock_process.assert_not_called()
    mock_ingest.assert_called_once_with(12345, 67890, "update", "webhook")
