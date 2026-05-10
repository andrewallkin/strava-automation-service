from __future__ import annotations

import httpx

from app.config import get_settings

TELEGRAM_BASE_URL = "https://api.telegram.org"


class CoachTelegramService:
    def __init__(self) -> None:
        self._settings = get_settings()

    @property
    def base_url(self) -> str:
        return f"{TELEGRAM_BASE_URL}/bot{self._settings.coach_telegram_bot_token}"

    def send_message(self, chat_id: int, text: str) -> None:
        httpx.post(
            f"{self.base_url}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=30,
        ).raise_for_status()
