import asyncio
from unittest.mock import AsyncMock, MagicMock, call, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.services.webhook_registration import (
    ensure_webhooks_registered,
    register_strava_subscription,
    register_telegram_webhook,
)


def _settings() -> MagicMock:
    settings = MagicMock()
    settings.public_base_url = "https://example.com"
    settings.app_env = "production"
    settings.strava_client_id = "strava-client-id"
    settings.strava_client_secret = "strava-client-secret"
    settings.strava_webhook_verify_token = "verify-token"
    settings.strava_webhook_url = "https://example.com/api/strava/webhook"
    settings.telegram_bot_token = "telegram-bot-token"
    settings.telegram_webhook_secret = "telegram-secret"
    settings.telegram_webhook_url = "https://example.com/api/telegram/activityadmin/webhook/telegram-secret"
    return settings


def _response(body: dict | list | None = None, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = body if body is not None else {}
    response.text = f"status={status_code}"
    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}", request=MagicMock(), response=response
        )
    return response


def test_strava_webhook_url_builds_callback_url() -> None:
    settings = Settings(app_env="production", public_base_url="https://example.com/")
    assert settings.strava_webhook_url == "https://example.com/api/strava/webhook"


def test_strava_webhook_url_empty_without_public_base_url() -> None:
    assert Settings(app_env="production").strava_webhook_url == ""


def test_register_strava_subscription_noop_when_callback_matches() -> None:
    listing = _response(body=[{"id": 11, "callback_url": "https://example.com/api/strava/webhook"}])

    with patch("app.services.webhook_registration.httpx.request", return_value=listing) as request:
        register_strava_subscription(_settings())

    assert request.call_count == 1
    assert request.call_args.args == ("GET", "https://www.strava.com/api/v3/push_subscriptions")
    assert request.call_args.kwargs["params"] == {
        "client_id": "strava-client-id",
        "client_secret": "strava-client-secret",
    }


def test_register_strava_subscription_replaces_stale_subscription() -> None:
    listing = _response(body=[{"id": 7, "callback_url": "https://old.example.com/api/strava/webhook"}])

    with patch(
        "app.services.webhook_registration.httpx.request",
        side_effect=[listing, _response(), _response(body={"id": 99})],
    ) as request:
        register_strava_subscription(_settings())

    delete_call, create_call = request.call_args_list[1], request.call_args_list[2]
    assert delete_call.args == ("DELETE", "https://www.strava.com/api/v3/push_subscriptions/7")
    assert delete_call.kwargs["params"] == {
        "client_id": "strava-client-id",
        "client_secret": "strava-client-secret",
    }
    assert create_call.args == ("POST", "https://www.strava.com/api/v3/push_subscriptions")
    assert create_call.kwargs["data"] == {
        "client_id": "strava-client-id",
        "client_secret": "strava-client-secret",
        "callback_url": "https://example.com/api/strava/webhook",
        "verify_token": "verify-token",
    }


def test_register_strava_subscription_creates_when_none_exists() -> None:
    with patch(
        "app.services.webhook_registration.httpx.request",
        side_effect=[_response(body=[]), _response(body={"id": 5})],
    ) as request:
        register_strava_subscription(_settings())

    assert [request_call.args[0] for request_call in request.call_args_list] == ["GET", "POST"]


def test_register_strava_subscription_tolerates_listing_failure() -> None:
    with patch(
        "app.services.webhook_registration.httpx.request",
        side_effect=[_response(status_code=500), _response(body={"id": 5})],
    ) as request:
        register_strava_subscription(_settings())

    assert [request_call.args[0] for request_call in request.call_args_list] == ["GET", "POST"]


def test_register_strava_subscription_survives_stale_delete_failure() -> None:
    listing = _response(body=[{"id": 7, "callback_url": "https://old.example.com/api/strava/webhook"}])

    with patch(
        "app.services.webhook_registration.httpx.request",
        side_effect=[listing, _response(status_code=500), _response(body={"id": 8})],
    ) as request:
        register_strava_subscription(_settings())

    assert [request_call.args[0] for request_call in request.call_args_list] == ["GET", "DELETE", "POST"]


def test_register_strava_subscription_raises_when_create_fails() -> None:
    with (
        patch(
            "app.services.webhook_registration.httpx.request",
            side_effect=[_response(body=[]), _response(status_code=500)],
        ),
        pytest.raises(httpx.HTTPStatusError),
    ):
        register_strava_subscription(_settings())


def test_register_strava_subscription_raises_when_create_response_has_no_id() -> None:
    with (
        patch(
            "app.services.webhook_registration.httpx.request",
            side_effect=[_response(body=[]), _response(body={"errors": "bad"})],
        ),
        pytest.raises(RuntimeError),
    ):
        register_strava_subscription(_settings())


def test_register_telegram_webhook_posts_set_webhook() -> None:
    response = _response(body={"ok": True})

    with patch("app.services.webhook_registration.httpx.post", return_value=response) as post:
        register_telegram_webhook(_settings())

    assert post.call_args.args == ("https://api.telegram.org/bottelegram-bot-token/setWebhook",)
    assert post.call_args.kwargs["json"] == {
        "url": "https://example.com/api/telegram/activityadmin/webhook/telegram-secret"
    }
    response.raise_for_status.assert_called_once()


def test_register_telegram_webhook_raises_when_response_not_ok() -> None:
    response = _response(body={"ok": False, "description": "Unauthorized"})

    with (
        patch("app.services.webhook_registration.httpx.post", return_value=response),
        pytest.raises(RuntimeError),
    ):
        register_telegram_webhook(_settings())


def test_ensure_webhooks_registered_retries_until_success() -> None:
    settings = _settings()

    with (
        patch(
            "app.services.webhook_registration.register_strava_subscription",
            side_effect=[Exception("boom"), Exception("boom"), None],
        ) as strava_register,
        patch("app.services.webhook_registration.register_telegram_webhook") as telegram_register,
        patch("app.services.webhook_registration.asyncio.sleep", new_callable=AsyncMock) as sleep,
    ):
        asyncio.run(ensure_webhooks_registered(settings))

    assert strava_register.call_count == 3
    assert telegram_register.call_count == 3
    assert strava_register.call_args_list[0].args == (settings,)
    assert sleep.await_args_list == [call(30), call(60)]


def test_ensure_webhooks_registered_caps_retry_delay() -> None:
    settings = _settings()

    with (
        patch(
            "app.services.webhook_registration.register_strava_subscription",
            side_effect=[Exception("boom")] * 4 + [None],
        ) as strava_register,
        patch("app.services.webhook_registration.register_telegram_webhook") as telegram_register,
        patch("app.services.webhook_registration.asyncio.sleep", new_callable=AsyncMock) as sleep,
    ):
        asyncio.run(ensure_webhooks_registered(settings))

    assert strava_register.call_count == 5
    assert telegram_register.call_count == 5
    assert sleep.await_args_list == [call(30), call(60), call(300), call(300)]


def test_ensure_webhooks_registered_skips_when_public_base_url_missing() -> None:
    settings = _settings()
    settings.public_base_url = ""

    with (
        patch("app.services.webhook_registration.register_strava_subscription") as strava_register,
        patch("app.services.webhook_registration.register_telegram_webhook") as telegram_register,
    ):
        asyncio.run(ensure_webhooks_registered(settings))

    strava_register.assert_not_called()
    telegram_register.assert_not_called()


def test_ensure_webhooks_registered_skips_in_development() -> None:
    settings = _settings()
    settings.app_env = "development"

    with (
        patch("app.services.webhook_registration.register_strava_subscription") as strava_register,
        patch("app.services.webhook_registration.register_telegram_webhook") as telegram_register,
    ):
        asyncio.run(ensure_webhooks_registered(settings))

    strava_register.assert_not_called()
    telegram_register.assert_not_called()


def test_ensure_webhooks_registered_skips_strava_when_credentials_missing() -> None:
    settings = _settings()
    settings.strava_client_id = ""

    with (
        patch("app.services.webhook_registration.register_strava_subscription") as strava_register,
        patch("app.services.webhook_registration.register_telegram_webhook") as telegram_register,
    ):
        asyncio.run(ensure_webhooks_registered(settings))

    strava_register.assert_not_called()
    telegram_register.assert_called_once_with(settings)


def test_ensure_webhooks_registered_skips_telegram_when_credentials_missing() -> None:
    settings = _settings()
    settings.telegram_bot_token = ""

    with (
        patch("app.services.webhook_registration.register_strava_subscription") as strava_register,
        patch("app.services.webhook_registration.register_telegram_webhook") as telegram_register,
    ):
        asyncio.run(ensure_webhooks_registered(settings))

    strava_register.assert_called_once_with(settings)
    telegram_register.assert_not_called()


def test_lifespan_schedules_webhook_registration() -> None:
    settings = _settings()

    with (
        patch("app.config.get_settings", return_value=settings),
        patch("app.services.webhook_registration.ensure_webhooks_registered", new_callable=AsyncMock) as ensure,
    ):
        with TestClient(app) as client:
            response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert ensure.await_count == 1
    assert ensure.await_args.args == (settings,)


def test_app_serves_when_webhook_registration_fails() -> None:
    settings = _settings()

    with (
        patch("app.config.get_settings", return_value=settings),
        patch("app.services.webhook_registration.register_strava_subscription", side_effect=Exception("boom")),
        patch("app.services.webhook_registration.register_telegram_webhook", side_effect=Exception("boom")),
    ):
        with TestClient(app) as client:
            response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
