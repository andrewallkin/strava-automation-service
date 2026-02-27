"""Tests for session-based authentication on UI API routes."""

from fastapi.testclient import TestClient

from app.main import app


def test_ui_status_returns_401_without_session() -> None:
    """Protected UI endpoints return 401 when no session cookie is present."""
    client = TestClient(app)
    response = client.get("/api/ui/status")
    assert response.status_code == 401
    assert response.json()["detail"] == "Session expired or not authenticated"


def test_ui_summary_returns_401_without_session() -> None:
    """Summary endpoint requires session."""
    client = TestClient(app)
    response = client.get("/api/ui/summary")
    assert response.status_code == 401


def test_disconnect_returns_401_without_session() -> None:
    """Disconnect endpoint requires session."""
    client = TestClient(app)
    response = client.delete("/api/auth/strava/disconnect")
    assert response.status_code == 401


def test_health_unchanged_without_session() -> None:
    """Health endpoint remains public (no session required)."""
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
