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
        activity: dict | None = None,
    ) -> int:
        if activity:
            lines = []
            name = activity.get("name", "")
            distance_m = activity.get("distance", 0) or 0
            moving_time_s = activity.get("moving_time", 0) or 0
            elevation_m = activity.get("total_elevation_gain", 0) or 0

            if distance_m > 0:
                km = distance_m / 1000
                if moving_time_s > 0:
                    pace_sec_per_km = moving_time_s / km
                    pace_min = int(pace_sec_per_km // 60)
                    pace_sec = int(pace_sec_per_km % 60)
                    mins = moving_time_s // 60
                    secs = moving_time_s % 60
                    lines.append(f"🏃 {km:.2f}km in {mins}:{secs:02d} ({pace_min}:{pace_sec:02d}/km)")
                else:
                    lines.append(f"🏃 {km:.2f}km")
            if elevation_m > 0:
                lines.append(f"⛰️ {int(elevation_m)}m elevation")
            if name:
                lines.append(f"📝 \"{name}\"")
            lines.append("\nWhich shoes did you wear? 👟")
            text = "\n".join(lines)
        else:
            text = "Nice run 🏃 Which shoes did you wear? 👟"

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
                "text": text,
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
