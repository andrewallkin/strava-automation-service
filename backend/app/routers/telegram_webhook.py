import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.logging_utils import fmt_dist
from app.models import Gear, PendingActivity, StravaActivity, User
from app.services.activity_service import clear_pending_activity, log_event
from app.services.strava_profile_service import sync_gear_detail
from app.services.strava_service import StravaService
from app.services.telegram_messages import format_help
from app.services.telegram_queries import recent_text, shoes_text, streak_text, week_text
from app.services.telegram_service import TelegramService
from app.services.telegram_state import JOHANNESBURG, active_rename, arm_rename, clear_rename

log = logging.getLogger("telegram")

router = APIRouter(prefix="/api/telegram/activityadmin", tags=["telegram-webhook"])


def _parse_callback_data(raw: str) -> tuple[int, str]:
    # Expected format: a:<activity_id>:g:<gear_id>
    parts = raw.split(":")
    if len(parts) != 4 or parts[0] != "a" or parts[2] != "g":
        raise ValueError("Invalid callback_data")
    return int(parts[1]), parts[3]


def _parse_rename_callback(raw: str) -> int:
    parts = raw.split(":")
    if len(parts) != 2 or parts[0] != "r":
        raise ValueError("Invalid callback_data")
    return int(parts[1])


COMMANDS = {"/shoes", "/week", "/recent", "/streak", "/help", "/cancel"}


def _command_name(text: str) -> str | None:
    token = text.strip().split(maxsplit=1)[0] if text.strip() else ""
    if not token.startswith("/"):
        return None
    name = token.split("@", 1)[0].lower()
    if name in COMMANDS:
        return name
    return "unknown"


def _require_allowed(settings, user_id: int | None) -> None:
    if settings.telegram_allowed_user_id and user_id != settings.telegram_allowed_user_id:
        raise HTTPException(status_code=403, detail="Unauthorized telegram user")


def _run_command(db: Session, chat_id: int, command: str) -> None:
    telegram = TelegramService()
    if command == "/cancel":
        telegram.send_message(chat_id, "Rename cancelled.")
        return
    if command == "/help" or command == "unknown":
        telegram.send_message(chat_id, format_help() if command == "/help" else "Send /help to see commands.")
        return
    user = db.scalar(select(User).limit(1))
    if not user:
        raise HTTPException(status_code=400, detail="No authenticated Strava user available")
    today = datetime.now(JOHANNESBURG).date()
    if command == "/week":
        telegram.send_message(chat_id, week_text(db, user, today))
    elif command == "/recent":
        telegram.send_message(chat_id, recent_text(db, user))
    elif command == "/streak":
        telegram.send_message(chat_id, streak_text(db, user, today))
    elif command == "/shoes":
        strava = StravaService()
        shoes = strava.sync_gear_cache(db, user=user)
        for shoe in shoes:
            sync_gear_detail(db, user, shoe["id"], strava)
        db.commit()
        telegram.send_message(chat_id, shoes_text(db))


def _apply_rename(db: Session, chat_id: int, activity_id: int, text: str) -> dict:
    name = text.strip()
    telegram = TelegramService()
    if not name or len(name) > 255:
        telegram.send_message(chat_id, "Send a name up to 255 characters.")
        return {"status": "rename_rejected"}
    user = db.scalar(select(User).limit(1))
    if not user:
        raise HTTPException(status_code=400, detail="No authenticated Strava user available")
    try:
        StravaService().update_activity(db, activity_id=activity_id, payload={"name": name}, user=user)
    except Exception as exc:
        log_event(db, "telegram_rename", "error", f"Rename failed: {exc}", {"activity_id": activity_id})
        telegram.send_message(chat_id, "Something went wrong. Try again.")
        return {"status": "error"}
    stored = db.get(StravaActivity, activity_id)
    if stored is not None:
        stored.name = name
        db.commit()
    clear_rename(db, chat_id)
    telegram.send_message(chat_id, f'Renamed to "{name}".')
    return {"status": "renamed", "activity_id": activity_id}


def _handle_message(db: Session, settings, message: dict) -> dict:
    from_user = message.get("from", {})
    _require_allowed(settings, from_user.get("id"))
    chat_id = (message.get("chat") or {}).get("id") or from_user.get("id")
    text = message.get("text") or ""
    command = _command_name(text)
    if command:
        clear_rename(db, chat_id)
        _run_command(db, chat_id, command)
        return {"status": "command", "command": command}
    waiting = active_rename(db, chat_id, datetime.now(timezone.utc))
    if waiting:
        return _apply_rename(db, chat_id, waiting.activity_id, text)
    TelegramService().send_message(chat_id, "Send /help to see commands.")
    return {"status": "ignored", "reason": "unknown text"}


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
    message = payload.get("message")
    if message:
        return _handle_message(db, settings, message)

    callback = payload.get("callback_query")
    if not callback:
        return {"status": "ignored", "reason": "no callback_query"}

    from_user = callback.get("from", {})
    _require_allowed(settings, from_user.get("id"))
    data = callback.get("data", "")
    if data.startswith("r:"):
        try:
            activity_id = _parse_rename_callback(data)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        chat_id = from_user.get("id")
        arm_rename(db, chat_id, activity_id, datetime.now(timezone.utc))
        telegram = TelegramService()
        telegram.answer_callback(callback_query_id=callback["id"], text="Send the new name")
        telegram.send_message(chat_id, "Send the new name. /cancel to stop.")
        return {"status": "rename_armed", "activity_id": activity_id}

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
