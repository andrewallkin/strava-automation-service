from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.services.activity_service import log_event
from app.services.webhook_processor import process_activity

router = APIRouter(prefix="/api/strava", tags=["strava-webhook"])


@router.get("/webhook")
def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
) -> dict:
    settings = get_settings()
    if hub_mode != "subscribe" or hub_token != settings.strava_webhook_verify_token:
        raise HTTPException(status_code=403, detail="Webhook verification failed")
    return {"hub.challenge": hub_challenge}


@router.post("/webhook")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict:
    payload = await request.json()
    log_event(db, "strava_webhook_received", "ok", "Strava webhook received", payload)

    if payload.get("object_type") != "activity":
        return {"status": "ignored", "reason": "non-activity object"}
    if payload.get("aspect_type") != "create":
        return {"status": "ignored", "reason": "non-create event"}

    activity_id = payload.get("object_id")
    owner_id = payload.get("owner_id")
    if not activity_id:
        return {"status": "ignored", "reason": "missing object_id"}

    settings = get_settings()
    if settings.strava_allowed_athlete_id and (
        owner_id is None or int(owner_id) != settings.strava_allowed_athlete_id
    ):
        return {"status": "ignored", "reason": "unauthorized_owner"}

    background_tasks.add_task(
        process_activity,
        int(activity_id),
        int(owner_id) if owner_id else None,
        0,
    )
    return {"status": "queued", "activity_id": activity_id}
