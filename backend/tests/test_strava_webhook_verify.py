from fastapi.testclient import TestClient

from app.main import app


def test_strava_webhook_verify_fail_without_token() -> None:
    client = TestClient(app)
    response = client.get(
        "/api/strava/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": "bad", "hub.challenge": "123"},
    )
    assert response.status_code == 403
