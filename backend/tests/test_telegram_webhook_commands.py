import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db import get_db
from app.main import app
from app.models import EventLog, Gear, PendingActivity, StravaActivity, TelegramRenameWait, User
from app.routers import telegram_webhook


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(element, compiler, **kw):  # noqa: ARG001
    return "JSON"


@pytest.fixture
def api(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in (
        User.__table__,
        Gear.__table__,
        PendingActivity.__table__,
        EventLog.__table__,
        StravaActivity.__table__,
        TelegramRenameWait.__table__,
    ):
        table.create(engine)
    session = sessionmaker(bind=engine)()
    session.add(User(id=1, strava_athlete_id=7, telegram_user_id=5))
    session.commit()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    settings = Settings(
        telegram_webhook_secret="secret",
        telegram_allowed_user_id=5,
        telegram_bot_token="token",
        app_secret_key="test-secret-test-secret-test-secret",
    )
    monkeypatch.setattr(telegram_webhook, "get_settings", lambda: settings)
    sent: list[tuple[int, str]] = []

    def send_message(self, chat_id, text, **kwargs):  # noqa: ARG001
        sent.append((chat_id, text))

    def answer_callback(self, **kwargs):  # noqa: ARG001
        return None

    def update_activity(self, db, activity_id, payload, user):  # noqa: ARG001
        return payload

    monkeypatch.setattr(telegram_webhook.TelegramService, "send_message", send_message)
    monkeypatch.setattr(telegram_webhook.TelegramService, "answer_callback", answer_callback)
    monkeypatch.setattr(telegram_webhook.StravaService, "update_activity", update_activity)
    monkeypatch.setattr(
        telegram_webhook.StravaService,
        "sync_gear_cache",
        lambda self, db, user: [{"id": "g1"}],
    )
    monkeypatch.setattr(telegram_webhook, "sync_gear_detail", lambda db, user, gear_id, strava: None)

    client = TestClient(app)
    yield {"client": client, "db": session, "sent": sent, "updates": []}
    app.dependency_overrides.pop(get_db, None)
    session.close()


def _post(api, body: dict):
    return api["client"].post("/api/telegram/activityadmin/webhook/secret", json=body)


def test_week_command_sends_week_text(api, monkeypatch) -> None:
    monkeypatch.setattr(telegram_webhook, "week_text", lambda db, user, today: "WEEK")
    response = _post(api, {"message": {"text": "/week", "chat": {"id": 5}, "from": {"id": 5}}})
    assert response.status_code == 200
    assert api["sent"] == [(5, "WEEK")]


def test_lookup_commands_send_their_text(api, monkeypatch) -> None:
    monkeypatch.setattr(telegram_webhook, "shoes_text", lambda db: "SHOES")
    monkeypatch.setattr(telegram_webhook, "recent_text", lambda db, user: "RECENT")
    monkeypatch.setattr(telegram_webhook, "streak_text", lambda db, user, today: "STREAK")
    monkeypatch.setattr(telegram_webhook, "format_help", lambda: "HELP")
    for command, expected in (("/shoes", "SHOES"), ("/recent", "RECENT"), ("/streak", "STREAK"), ("/help", "HELP")):
        api["sent"].clear()
        _post(api, {"message": {"text": command, "chat": {"id": 5}, "from": {"id": 5}}})
        assert api["sent"] == [(5, expected)]


def test_rename_flow_updates_strava_and_local_name(api, monkeypatch) -> None:
    updates: list[dict] = []

    def update_activity(self, db, activity_id, payload, user):  # noqa: ARG001
        updates.append({"activity_id": activity_id, "payload": payload})
        return payload

    monkeypatch.setattr(telegram_webhook.StravaService, "update_activity", update_activity)
    api["db"].add(StravaActivity(activity_id=42, athlete_id=7, name="Old"))
    api["db"].commit()
    armed = _post(api, {"callback_query": {"id": "cb", "data": "r:42", "from": {"id": 5}}})
    assert armed.json()["status"] == "rename_armed"
    assert api["sent"][-1] == (5, "Send the new name. /cancel to stop.")
    renamed = _post(api, {"message": {"text": "Lunch run", "chat": {"id": 5}, "from": {"id": 5}}})
    assert renamed.json()["status"] == "renamed"
    assert updates == [{"activity_id": 42, "payload": {"name": "Lunch run"}}]
    assert api["sent"][-1] == (5, 'Renamed to "Lunch run".')
    assert api["db"].get(StravaActivity, 42).name == "Lunch run"


def test_cancel_does_not_rename(api, monkeypatch) -> None:
    updates: list[dict] = []
    monkeypatch.setattr(
        telegram_webhook.StravaService,
        "update_activity",
        lambda self, db, activity_id, payload, user: updates.append(payload),
    )
    _post(api, {"callback_query": {"id": "cb", "data": "r:42", "from": {"id": 5}}})
    _post(api, {"message": {"text": "/cancel", "chat": {"id": 5}, "from": {"id": 5}}})
    assert updates == []


def test_long_and_blank_names_keep_the_wait(api, monkeypatch) -> None:
    updates: list[dict] = []
    monkeypatch.setattr(
        telegram_webhook.StravaService,
        "update_activity",
        lambda self, db, activity_id, payload, user: updates.append(payload),
    )
    _post(api, {"callback_query": {"id": "cb", "data": "r:42", "from": {"id": 5}}})
    _post(api, {"message": {"text": "x" * 256, "chat": {"id": 5}, "from": {"id": 5}}})
    _post(api, {"message": {"text": "   ", "chat": {"id": 5}, "from": {"id": 5}}})
    assert updates == []
    renamed = _post(api, {"message": {"text": "Ok", "chat": {"id": 5}, "from": {"id": 5}}})
    assert renamed.json()["status"] == "renamed"


def test_rejected_user_is_forbidden(api) -> None:
    response = _post(api, {"message": {"text": "/week", "chat": {"id": 9}, "from": {"id": 9}}})
    assert response.status_code == 403


def test_failed_rename_is_reported(api, monkeypatch) -> None:
    def explode(self, db, activity_id, payload, user):  # noqa: ARG001
        raise RuntimeError("strava down")

    monkeypatch.setattr(telegram_webhook.StravaService, "update_activity", explode)
    _post(api, {"callback_query": {"id": "cb", "data": "r:42", "from": {"id": 5}}})
    response = _post(api, {"message": {"text": "Lunch run", "chat": {"id": 5}, "from": {"id": 5}}})
    assert response.json()["status"] == "error"
    assert api["sent"][-1] == (5, "Something went wrong. Try again.")
    assert api["db"].query(EventLog).count() == 1
