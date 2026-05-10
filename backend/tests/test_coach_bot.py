from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.db import get_db
from app.deps import require_jwt_user
from app.main import app
from app.models import User
from app.routers.telegram_coach_webhook import _parse_start_code
from app.services.coach_conversation_store import cap_by_user_turns


def test_parse_start_code() -> None:
    assert _parse_start_code("/start ABC123") == "ABC123"
    assert _parse_start_code("/start") is None
    assert _parse_start_code("hello") is None


def test_cap_by_user_turns_keeps_last_user_turns() -> None:
    history = [
        {"role": "user", "content": [{"type": "input_text", "text": "u1"}]},
        {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "a1"}]},
        {"role": "user", "content": [{"type": "input_text", "text": "u2"}]},
        {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "a2"}]},
        {"role": "user", "content": [{"type": "input_text", "text": "u3"}]},
        {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "a3"}]},
    ]
    capped = cap_by_user_turns(history, 2)
    assert capped[0]["content"][0]["text"] == "u2"
    assert capped[-1]["content"][0]["text"] == "a3"


def test_coach_link_code_endpoint() -> None:
    fake_user = User(id=11)
    app.dependency_overrides[require_jwt_user] = lambda: fake_user
    try:
        with patch("app.routers.ui_api.get_redis_client") as mock_redis, patch(
            "app.routers.ui_api.CoachLinkService.issue_code",
            return_value=("ABC123", 600),
        ) as mock_issue:
            mock_redis.return_value = MagicMock()
            client = TestClient(app)
            response = client.post("/api/ui/coach/link-code")
            assert response.status_code == 200
            assert response.json() == {"code": "ABC123", "expires_in_seconds": 600}
            mock_issue.assert_called_once_with(11)
    finally:
        app.dependency_overrides.pop(require_jwt_user, None)


def test_coach_webhook_start_links_telegram_user() -> None:
    settings = SimpleNamespace(
        coach_telegram_webhook_secret="coach-secret",
        coach_telegram_allowed_user_id=12345,
        coach_conversation_history_user_turn_limit=20,
    )
    user = User(id=7, telegram_user_id=None)
    mock_db = MagicMock()
    mock_db.scalar.side_effect = [user, None]

    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        payload = {
            "message": {
                "text": "/start ABC123",
                "from": {"id": 12345},
                "chat": {"id": 12345},
            }
        }
        with patch("app.routers.telegram_coach_webhook.get_settings", return_value=settings), patch(
            "app.routers.telegram_coach_webhook.get_redis_client"
        ) as mock_redis, patch(
            "app.routers.telegram_coach_webhook.CoachLinkService.consume_code",
            return_value=7,
        ), patch(
            "app.routers.telegram_coach_webhook.CoachTelegramService.send_message"
        ) as mock_send:
            mock_redis.return_value = MagicMock()
            response = TestClient(app).post("/api/telegram/coach/webhook/coach-secret", json=payload)
            assert response.status_code == 200
            assert response.json()["status"] == "linked"
            assert user.telegram_user_id == 12345
            mock_db.commit.assert_called_once()
            mock_send.assert_called()
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_coach_webhook_message_uses_history_and_sends_reply() -> None:
    settings = SimpleNamespace(
        coach_telegram_webhook_secret="coach-secret",
        coach_telegram_allowed_user_id=12345,
        coach_conversation_history_user_turn_limit=20,
    )
    user = User(id=9, telegram_user_id=12345)
    coach_settings = SimpleNamespace(
        vector_store_id="vs_123",
        agent_name="Coach",
        agent_instructions="Be concise",
        openai_model="gpt-4.1-mini",
    )
    mock_db = MagicMock()
    mock_db.scalar.side_effect = [user]

    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        payload = {
            "message": {
                "text": "How was my run?",
                "from": {"id": 12345},
                "chat": {"id": 12345},
            }
        }
        with patch("app.routers.telegram_coach_webhook.get_settings", return_value=settings), patch(
            "app.routers.telegram_coach_webhook.get_redis_client"
        ) as mock_redis, patch(
            "app.routers.telegram_coach_webhook.get_or_create_coach_settings",
            return_value=coach_settings,
        ), patch(
            "app.routers.telegram_coach_webhook.CoachOpenAIService.run_turn",
            new=AsyncMock(
                return_value=("Nice session.", [{"role": "user"}, {"type": "message", "role": "assistant"}])
            ),
        ) as mock_run_turn, patch(
            "app.routers.telegram_coach_webhook.CoachTelegramService.send_message"
        ) as mock_send:
            mock_store = MagicMock()
            mock_store.get_history.return_value = []
            with patch("app.routers.telegram_coach_webhook.CoachConversationStore", return_value=mock_store):
                mock_redis.return_value = MagicMock()
                response = TestClient(app).post("/api/telegram/coach/webhook/coach-secret", json=payload)
                assert response.status_code == 200
                assert response.json()["status"] == "ok"
                mock_run_turn.assert_called_once()
                mock_store.append_history.assert_called_once_with(
                    9,
                    [{"role": "user"}, {"type": "message", "role": "assistant"}],
                    20,
                )
                mock_send.assert_called_with(12345, "Nice session.", content_is_markup=True)
    finally:
        app.dependency_overrides.pop(get_db, None)
