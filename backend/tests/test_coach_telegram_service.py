from types import SimpleNamespace
from unittest.mock import patch

import httpx

from app.services.coach_telegram_service import CoachTelegramService


def test_send_message_retries_invalid_markup_as_escaped_plain_text() -> None:
    request = httpx.Request("POST", "https://api.telegram.org/bottoken/sendMessage")
    rejected = httpx.Response(
        400,
        json={"ok": False, "description": "Bad Request: can't parse entities"},
        request=request,
    )
    accepted = httpx.Response(200, json={"ok": True}, request=request)

    with patch(
        "app.services.coach_telegram_service.get_settings",
        return_value=SimpleNamespace(coach_telegram_bot_token="token"),
    ), patch("app.services.coach_telegram_service.httpx.post", side_effect=[rejected, accepted]) as mock_post:
        CoachTelegramService().send_message(12345, "Great run (easy)!", content_is_markup=True)

    assert mock_post.call_count == 2
    assert mock_post.call_args_list[0].kwargs["json"] == {
        "chat_id": 12345,
        "text": "Great run (easy)!",
        "parse_mode": "MarkdownV2",
    }
    assert mock_post.call_args_list[1].kwargs["json"] == {
        "chat_id": 12345,
        "text": r"Great run \(easy\)\!",
        "parse_mode": "MarkdownV2",
    }
