import httpx

from app.config import get_settings

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
    ) -> int:
        keyboard = [
            [
                {
                    "text": shoe.get("name", shoe["id"]),
                    "callback_data": f"a:{activity_id}:g:{shoe['id']}",
                }
            ]
            for shoe in shoes
        ]
        resp = httpx.post(
            f"{self.base_url}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": "Nice run. Which shoes did you use?",
                "reply_markup": {"inline_keyboard": keyboard},
            },
            timeout=20,
        )
        resp.raise_for_status()
        return int(resp.json()["result"]["message_id"])

    def send_message(self, chat_id: int, text: str) -> None:
        httpx.post(
            f"{self.base_url}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=20,
        ).raise_for_status()

    def answer_callback(self, callback_query_id: str, text: str = "Saved") -> None:
        httpx.post(
            f"{self.base_url}/answerCallbackQuery",
            json={"callback_query_id": callback_query_id, "text": text},
            timeout=20,
        ).raise_for_status()
