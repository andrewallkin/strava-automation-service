from __future__ import annotations

import httpx
import logging

from app.config import get_settings
from app.services.telegram_markdown import MARKDOWN_V2, escape_markdown_v2

TELEGRAM_BASE_URL = "https://api.telegram.org"
log = logging.getLogger("coach.telegram")


class CoachTelegramService:
    def __init__(self) -> None:
        self._settings = get_settings()

    @property
    def base_url(self) -> str:
        return f"{TELEGRAM_BASE_URL}/bot{self._settings.coach_telegram_bot_token}"

    def send_message(self, chat_id: int, text: str, *, content_is_markup: bool = False) -> None:
        log.info("Sending Telegram coach message chat_id=%s text_length=%s", chat_id, len(text))
        outbound = text if content_is_markup else escape_markdown_v2(text)
        response = httpx.post(
            f"{self.base_url}/sendMessage",
            json={"chat_id": chat_id, "text": outbound, "parse_mode": MARKDOWN_V2},
            timeout=30,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if not content_is_markup or exc.response.status_code != 400:
                raise

            log.warning(
                "Telegram rejected MarkdownV2 coach message; retrying as escaped plain text "
                "chat_id=%s response_body=%s",
                chat_id,
                exc.response.text[:500],
            )
            httpx.post(
                f"{self.base_url}/sendMessage",
                json={"chat_id": chat_id, "text": escape_markdown_v2(text), "parse_mode": MARKDOWN_V2},
                timeout=30,
            ).raise_for_status()
        log.info("Telegram coach message sent successfully chat_id=%s", chat_id)
