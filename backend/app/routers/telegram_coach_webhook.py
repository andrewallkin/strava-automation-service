from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User
from app.services.coach_conversation_store import CoachConversationStore
from app.services.coach_link_service import CoachLinkService
from app.services.coach_openai_service import CoachOpenAIService
from app.services.coach_settings_service import get_or_create_coach_settings
from app.services.coach_telegram_service import CoachTelegramService
from app.services.redis_client import get_redis_client

log = logging.getLogger("telegram")

router = APIRouter(prefix="/api/telegram/coach", tags=["telegram-coach-webhook"])


def _parse_start_code(text: str) -> str | None:
    parts = text.strip().split(maxsplit=1)
    if not parts:
        return None
    if not parts[0].startswith("/start"):
        return None
    if len(parts) < 2:
        return None
    code = parts[1].strip()
    return code or None


@router.post("/webhook/{secret}")
async def coach_telegram_webhook(
    request: Request,
    secret: str = Path(...),
    db: Session = Depends(get_db),
) -> dict:
    settings = get_settings()
    if secret != settings.coach_telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    payload = await request.json()
    message = payload.get("message")
    if not message:
        return {"status": "ignored", "reason": "no message"}

    from_user = message.get("from", {}) or {}
    from_user_id = from_user.get("id")
    if not isinstance(from_user_id, int):
        return {"status": "ignored", "reason": "no from user id"}

    if settings.coach_telegram_allowed_user_id and from_user_id != settings.coach_telegram_allowed_user_id:
        raise HTTPException(status_code=403, detail="Unauthorized telegram user")

    chat = message.get("chat", {}) or {}
    chat_id = chat.get("id")
    if not isinstance(chat_id, int):
        chat_id = from_user_id

    telegram = CoachTelegramService()
    text = (message.get("text") or "").strip()
    start_code = _parse_start_code(text)
    redis_client = get_redis_client()

    if start_code is not None:
        link_service = CoachLinkService(redis_client)
        linked_user_id = link_service.consume_code(start_code)
        if not linked_user_id:
            telegram.send_message(chat_id, "That link code is invalid or expired. Generate a new code in Settings.")
            return {"status": "ignored", "reason": "invalid start code"}

        user = db.scalar(select(User).where(User.id == linked_user_id).limit(1))
        if not user:
            telegram.send_message(chat_id, "I couldn't find your account. Please regenerate a link code.")
            return {"status": "ignored", "reason": "missing user for start code"}

        existing_user = db.scalar(
            select(User).where(User.telegram_user_id == from_user_id, User.id != user.id).limit(1)
        )
        if existing_user:
            telegram.send_message(
                chat_id,
                "This Telegram account is already linked to a different user.",
            )
            return {"status": "ignored", "reason": "telegram user already linked"}

        if user.telegram_user_id and user.telegram_user_id != from_user_id:
            telegram.send_message(
                chat_id,
                "This app user is already linked to a different Telegram account.",
            )
            return {"status": "ignored", "reason": "app user already linked to different telegram user"}

        user.telegram_user_id = from_user_id
        db.commit()
        telegram.send_message(chat_id, "Your coach bot is linked. Send me a message to start chatting.")
        return {"status": "linked", "user_id": user.id}

    user = db.scalar(select(User).where(User.telegram_user_id == from_user_id).limit(1))
    if not user:
        telegram.send_message(
            chat_id,
            "Your Telegram account is not linked yet. Generate a link code in Settings and send /start <code>.",
        )
        return {"status": "ignored", "reason": "telegram user not linked"}

    if not text:
        return {"status": "ignored", "reason": "empty text"}

    coach_settings = get_or_create_coach_settings(db, user)
    history_store = CoachConversationStore(redis_client)
    history = history_store.get_history(user.id)
    turn_limit = max(settings.coach_conversation_history_user_turn_limit, 1)

    try:
        reply_text, new_items = await CoachOpenAIService().run_turn(
            db=db,
            user=user,
            coach_settings=coach_settings,
            history=history,
            user_message=text,
        )
    except ValueError as exc:
        telegram.send_message(chat_id, str(exc))
        return {"status": "error", "detail": str(exc)}
    except Exception:
        log.exception("Coach bot failed to process message")
        telegram.send_message(chat_id, "I hit an error while processing that. Please try again.")
        return {"status": "error", "detail": "processing_failed"}

    history_store.append_history(user.id, new_items, turn_limit)
    telegram.send_message(chat_id, reply_text)
    return {"status": "ok"}
