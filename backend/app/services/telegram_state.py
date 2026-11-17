"""Rename waits and the Sunday digest decision."""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TelegramRenameWait

JOHANNESBURG = ZoneInfo("Africa/Johannesburg")
RENAME_WAIT = timedelta(minutes=10)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def arm_rename(db: Session, chat_id: int, activity_id: int, now: datetime) -> None:
    expires_at = _aware(now) + RENAME_WAIT
    existing = db.scalar(select(TelegramRenameWait).where(TelegramRenameWait.chat_id == chat_id))
    if existing:
        existing.activity_id = activity_id
        existing.expires_at = expires_at
    else:
        db.add(TelegramRenameWait(chat_id=chat_id, activity_id=activity_id, expires_at=expires_at))
    db.commit()


def active_rename(db: Session, chat_id: int, now: datetime) -> TelegramRenameWait | None:
    row = db.scalar(select(TelegramRenameWait).where(TelegramRenameWait.chat_id == chat_id))
    if row is None or _aware(row.expires_at) <= _aware(now):
        return None
    return row


def clear_rename(db: Session, chat_id: int) -> None:
    row = db.scalar(select(TelegramRenameWait).where(TelegramRenameWait.chat_id == chat_id))
    if row is not None:
        db.delete(row)
        db.commit()


def digest_due(now: datetime, already_sent: set[date]) -> date | None:
    local = _aware(now).astimezone(JOHANNESBURG)
    if local.weekday() != 6 or local.hour < 18:
        return None
    monday = local.date() - timedelta(days=6)
    if monday in already_sent:
        return None
    return monday
