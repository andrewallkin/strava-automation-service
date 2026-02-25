import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import EventLog, PendingActivity, User
from app.services.webhook_processor import process_activity

router = APIRouter(prefix="/api/ui", tags=["ui"])


class SettingsUpdate(BaseModel):
    run_shoe_enabled: bool | None = None
    gym_hide_enabled: bool | None = None


@router.get("/status")
def status(db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).limit(1))
    if not user:
        raise HTTPException(status_code=404, detail="No user connected")
    return {
        "connected": bool(user.strava_athlete_id),
        "strava_athlete_id": user.strava_athlete_id,
        "run_shoe_enabled": user.run_shoe_enabled,
        "gym_hide_enabled": user.gym_hide_enabled,
    }


@router.patch("/settings")
def update_settings(body: SettingsUpdate, db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).limit(1))
    if not user:
        raise HTTPException(status_code=404, detail="No user connected")
    if body.run_shoe_enabled is not None:
        user.run_shoe_enabled = body.run_shoe_enabled
    if body.gym_hide_enabled is not None:
        user.gym_hide_enabled = body.gym_hide_enabled
    db.commit()
    db.refresh(user)
    return {
        "run_shoe_enabled": user.run_shoe_enabled,
        "gym_hide_enabled": user.gym_hide_enabled,
    }


@router.get("/summary")
def summary(db: Session = Depends(get_db)) -> dict:
    pending = len(db.scalars(select(PendingActivity)).all())
    latest = db.scalar(select(EventLog).order_by(EventLog.created_at.desc()).limit(1))
    runs_updated = db.scalar(
        select(func.count(EventLog.id)).where(
            EventLog.event_type == "run_action", EventLog.status == "ok"
        )
    ) or 0
    gym_hidden = db.scalar(
        select(func.count(EventLog.id)).where(
            EventLog.event_type == "gym_action", EventLog.status == "ok"
        )
    ) or 0
    return {
        "pending_count": pending,
        "last_event_at": latest.created_at.isoformat() if latest else None,
        "last_event_message": latest.message if latest else None,
        "runs_updated": runs_updated,
        "gym_hidden": gym_hidden,
    }


@router.get("/pending")
def pending(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(PendingActivity).order_by(PendingActivity.created_at.desc())).all()
    return [
        {
            "activity_id": row.activity_id,
            "telegram_message_id": row.telegram_message_id,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.get("/events")
def events(limit: int = Query(default=50, le=200), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(EventLog).order_by(EventLog.created_at.desc()).limit(limit)).all()
    return [
        {
            "id": row.id,
            "event_type": row.event_type,
            "status": row.status,
            "message": row.message,
            "payload": json.loads(row.payload) if row.payload else None,
            "correlation_id": row.correlation_id,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.post("/retry/{activity_id}")
def retry_activity(
    activity_id: int,
    background_tasks: BackgroundTasks,
    owner_id: int | None = None,
) -> dict:
    if activity_id < 1:
        raise HTTPException(status_code=400, detail="Invalid activity ID")
    background_tasks.add_task(process_activity, activity_id, owner_id, 0)
    return {"status": "queued", "activity_id": activity_id}
