import logging

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.logging_utils import fmt_dist
from app.models import Gear, PendingActivity, User
from app.services.activity_service import clear_pending_activity, log_event
from app.services.strava_service import StravaService
from app.services.telegram_service import TelegramService

log = logging.getLogger("telegram")

router = APIRouter(prefix="/api/telegram/activityadmin", tags=["telegram-webhook"])


def _parse_callback_data(raw: str) -> tuple[int, str]:
    # Expected format: a:<activity_id>:g:<gear_id>
    parts = raw.split(":")
    if len(parts) != 4 or parts[0] != "a" or parts[2] != "g":
        raise ValueError("Invalid callback_data")
    return int(parts[1]), parts[3]


@router.post("/webhook/{secret}")
async def telegram_webhook(
    request: Request,
    secret: str = Path(...),
    db: Session = Depends(get_db),
) -> dict:
    settings = get_settings()
    if secret != settings.telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    payload = await request.json()
    callback = payload.get("callback_query")
    if not callback:
        return {"status": "ignored", "reason": "no callback_query"}

    from_user = callback.get("from", {})
    if settings.telegram_allowed_user_id and from_user.get("id") != settings.telegram_allowed_user_id:
        raise HTTPException(status_code=403, detail="Unauthorized telegram user")

    try:
        activity_id, gear_id = _parse_callback_data(callback.get("data", ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log.info("Gear selection received | activity=%s gear_id=%s", activity_id, gear_id)

    pending = db.scalar(select(PendingActivity).where(PendingActivity.activity_id == activity_id))
    if not pending:
        return {"status": "ignored", "reason": "no pending activity"}

    strava = StravaService()
    user = db.scalar(select(User).limit(1))
    if not user:
        raise HTTPException(status_code=400, detail="No authenticated Strava user available")
    if not user.telegram_user_id:
        user.telegram_user_id = from_user.get("id")
        db.commit()

    strava.update_activity(db, activity_id=activity_id, payload={"gear_id": gear_id}, user=user)
    clear_pending_activity(db, activity_id)
    TelegramService().answer_callback(callback_query_id=callback["id"], text="Gear updated")

    gear_row = db.scalar(select(Gear).where(Gear.strava_gear_id == gear_id))
    shoe_name = gear_row.name if gear_row else gear_id
    chat_id = from_user.get("id") or user.telegram_user_id
    if chat_id:
        telegram = TelegramService()
        try:
            activity_data = strava.get_activity(db, activity_id=activity_id, user=user)
            activity_name = activity_data.get("name", "")
            distance_m = activity_data.get("distance", 0) or 0
            log.info(
                'Gear selected: %s → "%s" (%s) | activity=%s',
                shoe_name, activity_name, fmt_dist(distance_m), activity_id,
            )
            km_str = f"{distance_m / 1000:.2f}km" if distance_m else ""
            if km_str:
                confirmation = f"✅ {shoe_name} logged for your {km_str} run"
                if activity_name:
                    confirmation += f" \"{activity_name}\""
                confirmation += "! 💪"
            else:
                confirmation = f"✅ {shoe_name} logged. Smashed it 💪"
        except Exception:
            log.warning("Could not fetch activity details for log | activity=%s", activity_id)
            confirmation = f"✅ {shoe_name} logged. Smashed it 💪"
        telegram.send_message(chat_id, confirmation)

    log_event(db, "telegram_callback", "ok", "Gear updated from Telegram callback", payload)
    return {"status": "updated", "activity_id": activity_id, "gear_id": gear_id}
