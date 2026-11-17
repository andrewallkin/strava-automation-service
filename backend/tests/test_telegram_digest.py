from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.models import StravaActivity, User, WeeklyDigestSend
from app.services.telegram_digest import send_digest_if_due
from app.services.telegram_state import JOHANNESBURG
from app.services import telegram_digest


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(element, compiler, **kw):  # noqa: ARG001
    return "JSON"


def test_send_digest_once(monkeypatch) -> None:
    engine = create_engine("sqlite://")
    User.__table__.create(engine)
    StravaActivity.__table__.create(engine)
    WeeklyDigestSend.__table__.create(engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        session.add(User(id=1, strava_athlete_id=7, telegram_user_id=9))
        session.commit()

    monkeypatch.setattr(telegram_digest, "SessionLocal", session_factory)
    sent: list[tuple[int, str]] = []
    monkeypatch.setattr(
        telegram_digest.TelegramService,
        "send_message",
        lambda self, chat_id, text, **kwargs: sent.append((chat_id, text)),
    )
    sunday = datetime(2026, 11, 15, 18, 0, tzinfo=JOHANNESBURG)
    assert send_digest_if_due(sunday) is True
    assert sent[0][0] == 9
    assert "9–15 Nov" in sent[0][1]
    assert send_digest_if_due(sunday) is False
    assert len(sent) == 1
    with session_factory() as session:
        assert session.get(WeeklyDigestSend, sunday.date() - timedelta(days=6)) is not None
