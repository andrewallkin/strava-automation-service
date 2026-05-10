from __future__ import annotations

import httpx
import logging

from app.config import get_settings

TELEGRAM_BASE_URL = "https://api.telegram.org"
log = logging.getLogger("coach.telegram")


class CoachTelegramService:
    def __init__(self) -> None:
        self._settings = get_settings()

    @property
    def base_url(self) -> str:
        return f"{TELEGRAM_BASE_URL}/bot{self._settings.coach_telegram_bot_token}"

    def send_message(self, chat_id: int, text: str) -> None:
        log.info("Sending Telegram coach message chat_id=%s text_length=%s", chat_id, len(text))
        httpx.post(
            f"{self.base_url}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=30,
        ).raise_for_status()
        log.info("Telegram coach message sent successfully chat_id=%s", chat_id)
