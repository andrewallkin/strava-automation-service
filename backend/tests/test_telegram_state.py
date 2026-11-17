from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import TelegramRenameWait, WeeklyDigestSend
from app.services.telegram_state import active_rename, arm_rename, clear_rename, digest_due
from app.services.telegram_state import JOHANNESBURG


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    TelegramRenameWait.__table__.create(engine)
    WeeklyDigestSend.__table__.create(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def test_rename_wait_lasts_ten_minutes(db) -> None:
    armed = datetime(2026, 11, 15, 18, 0, tzinfo=timezone.utc)
    arm_rename(db, chat_id=5, activity_id=42, now=armed)
    assert active_rename(db, 5, armed + timedelta(minutes=9)) is not None
    assert active_rename(db, 5, armed + timedelta(minutes=10)) is None


def test_clear_rename_removes_the_wait(db) -> None:
    now = datetime(2026, 11, 15, 18, 0, tzinfo=timezone.utc)
    arm_rename(db, chat_id=5, activity_id=42, now=now)
    clear_rename(db, 5)
    assert active_rename(db, 5, now) is None


def test_digest_due_on_sunday_evening() -> None:
    sunday_evening = datetime(2026, 11, 15, 18, 0, tzinfo=JOHANNESBURG)
    monday = digest_due(sunday_evening, set())
    assert monday is not None
    assert monday.isoformat() == "2026-11-09"
    assert digest_due(sunday_evening, {monday}) is None
    assert digest_due(sunday_evening.replace(hour=17), set()) is None
    monday_morning = datetime(2026, 11, 16, 18, 0, tzinfo=JOHANNESBURG)
    assert digest_due(monday_morning, set()) is None
