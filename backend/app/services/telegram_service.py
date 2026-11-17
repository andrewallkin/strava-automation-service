import httpx

from app.config import get_settings
from app.services.telegram_markdown import MARKDOWN_V2, escape_markdown_v2
from app.services.telegram_messages import format_activity_receipt, format_run_card

TELEGRAM_BASE_URL = "https://api.telegram.org"


class TelegramService:
    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def base_url(self) -> str:
        return f"{TELEGRAM_BASE_URL}/bot{self.settings.telegram_bot_token}"

    def send_gear_selection_message(
        self,
        chat_id: int,
        activity_id: int,
        shoes: list[dict],
        activity: dict | None = None,
    ) -> int:
        text = format_run_card(activity) if activity else "Nice run 🏃 Which shoes did you wear? 👟"
        keyboard = [
            [
                {
                    "text": shoe.get("name", shoe["id"]),
                    "callback_data": f"a:{activity_id}:g:{shoe['id']}",
                }
            ]
            for shoe in shoes
        ]
        keyboard.append([{"text": "Rename", "callback_data": f"r:{activity_id}"}])
        outbound = escape_markdown_v2(text)
        resp = httpx.post(
            f"{self.base_url}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": outbound,
                "parse_mode": MARKDOWN_V2,
                "reply_markup": {"inline_keyboard": keyboard},
            },
            timeout=20,
        )
        resp.raise_for_status()
        return int(resp.json()["result"]["message_id"])

    def send_activity_receipt(self, chat_id: int, activity_id: int, activity: dict) -> int:
        resp = httpx.post(
            f"{self.base_url}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": escape_markdown_v2(format_activity_receipt(activity)),
                "parse_mode": MARKDOWN_V2,
                "reply_markup": {
                    "inline_keyboard": [[{"text": "Rename", "callback_data": f"r:{activity_id}"}]]
                },
            },
            timeout=20,
        )
        resp.raise_for_status()
        return int(resp.json()["result"]["message_id"])

    def send_message(self, chat_id: int, text: str, *, content_is_markup: bool = False) -> None:
        outbound = text if content_is_markup else escape_markdown_v2(text)
        httpx.post(
            f"{self.base_url}/sendMessage",
            json={"chat_id": chat_id, "text": outbound, "parse_mode": MARKDOWN_V2},
            timeout=20,
        ).raise_for_status()

    def answer_callback(self, callback_query_id: str, text: str = "Saved") -> None:
        httpx.post(
            f"{self.base_url}/answerCallbackQuery",
            json={
                "callback_query_id": callback_query_id,
                "text": escape_markdown_v2(text),
                "parse_mode": MARKDOWN_V2,
            },
            timeout=20,
        ).raise_for_status()
