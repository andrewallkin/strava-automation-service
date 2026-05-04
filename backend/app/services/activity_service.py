import json
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EventLog, Gear, PendingActivity


def log_event(
    db: Session,
    event_type: str,
    status: str,
    message: str,
    payload: dict | None = None,
    correlation_id: str | None = None,
) -> None:
    row = EventLog(
        event_type=event_type,
        status=status,
        message=message,
        payload=json.dumps(payload) if payload else None,
        correlation_id=correlation_id,
    )
    db.add(row)
    db.commit()


def upsert_gear(db: Session, strava_gear_id: str, name: str, is_default: bool = False) -> Gear:
    existing = db.scalar(select(Gear).where(Gear.strava_gear_id == strava_gear_id))
    if existing:
        existing.name = name
        existing.is_default = is_default
        db.commit()
        db.refresh(existing)
        return existing

    row = Gear(strava_gear_id=strava_gear_id, name=name, is_default=is_default)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_gear(db: Session) -> list[Gear]:
    return list(db.scalars(select(Gear).order_by(Gear.name.asc())).all())


def include_gear_in_shoe_vault(detail: dict[str, Any]) -> bool:
    """True if Strava DetailedGear is an active running shoe (exclude bikes/trainers and retired)."""
    if detail.get("retired") is True:
        return False
    if detail.get("frame_type") is not None:
        return False
    return True


def set_pending_activity(db: Session, activity_id: int, telegram_message_id: int) -> PendingActivity:
    existing = db.scalar(select(PendingActivity).where(PendingActivity.activity_id == activity_id))
    if existing:
        existing.telegram_message_id = telegram_message_id
        existing.created_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing

    row = PendingActivity(activity_id=activity_id, telegram_message_id=telegram_message_id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def clear_pending_activity(db: Session, activity_id: int) -> None:
    existing = db.scalar(select(PendingActivity).where(PendingActivity.activity_id == activity_id))
    if existing:
        db.delete(existing)
        db.commit()
