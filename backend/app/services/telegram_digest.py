"""Send the weekly Telegram summary once each Sunday evening."""

import logging
from datetime import datetime

from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import User, WeeklyDigestSend
from app.services.telegram_queries import week_text
from app.services.telegram_service import TelegramService
from app.services.telegram_state import JOHANNESBURG, digest_due

log = logging.getLogger("telegram")


def send_digest_if_due(now: datetime) -> bool:
    with SessionLocal() as db:
        sent = set(db.scalars(select(WeeklyDigestSend.week_start)).all())
        monday = digest_due(now, sent)
        if monday is None:
            return False
        user = db.scalar(select(User).limit(1))
        if user is None:
            return False
        chat_id = user.telegram_user_id or get_settings().telegram_allowed_user_id
        if not chat_id:
            return False
        text = week_text(db, user, now.astimezone(JOHANNESBURG).date())
        try:
            TelegramService().send_message(chat_id, text)
        except Exception:
            log.exception("Weekly digest send failed")
            return False
        db.add(WeeklyDigestSend(week_start=monday, sent_at=now))
        db.commit()
        return True
