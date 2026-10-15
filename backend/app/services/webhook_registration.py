import asyncio
import logging
from collections.abc import Callable

import httpx

from app.config import Settings

log = logging.getLogger("webhook")

STRAVA_BASE_URL = "https://www.strava.com"
TELEGRAM_BASE_URL = "https://api.telegram.org"

RETRY_DELAYS_SECONDS = (30, 60, 300)


def _strava_subscription_params(settings: Settings) -> dict[str, str]:
    return {"client_id": settings.strava_client_id, "client_secret": settings.strava_client_secret}


def _list_strava_subscriptions(settings: Settings) -> list:
    try:
        response = httpx.request(
            "GET",
            f"{STRAVA_BASE_URL}/api/v3/push_subscriptions",
            params=_strava_subscription_params(settings),
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, list) else []
    except Exception as exc:
        log.warning("Could not list Strava push subscriptions, attempting to create: %s", exc)
        return []


def register_strava_subscription(settings: Settings) -> None:
    callback_url = settings.strava_webhook_url
    subscriptions = _list_strava_subscriptions(settings)
    current = subscriptions[0] if subscriptions else None
    if current and current.get("callback_url") == callback_url:
        log.info("Strava webhook already registered (id=%s)", current.get("id"))
        return
    if current and current.get("id"):
        log.info("Removing stale Strava subscription (id=%s, url=%s)", current["id"], current.get("callback_url"))
        try:
            httpx.request(
                "DELETE",
                f"{STRAVA_BASE_URL}/api/v3/push_subscriptions/{current['id']}",
                params=_strava_subscription_params(settings),
                timeout=20,
            ).raise_for_status()
        except httpx.HTTPError as exc:
            log.warning("Could not remove stale Strava subscription: %s", exc)
    response = httpx.request(
        "POST",
        f"{STRAVA_BASE_URL}/api/v3/push_subscriptions",
        data={
            "client_id": settings.strava_client_id,
            "client_secret": settings.strava_client_secret,
            "callback_url": callback_url,
            "verify_token": settings.strava_webhook_verify_token,
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if "id" not in payload:
        raise RuntimeError(f"Strava webhook registration failed: {payload}")
    log.info("Strava webhook registered (id=%s)", payload["id"])


def register_telegram_webhook(settings: Settings) -> None:
    response = httpx.post(
        f"{TELEGRAM_BASE_URL}/bot{settings.telegram_bot_token}/setWebhook",
        json={"url": settings.telegram_webhook_url},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram setWebhook failed: {payload}")
    log.info("Telegram webhook registered (%s)", settings.telegram_webhook_url)


def _registration_steps(settings: Settings) -> list[tuple[str, Callable[[Settings], None]]]:
    steps: list[tuple[str, Callable[[Settings], None]]] = []
    if settings.strava_client_id and settings.strava_client_secret and settings.strava_webhook_verify_token:
        steps.append(("Strava", register_strava_subscription))
    else:
        log.info("Skipping Strava webhook registration: STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET and STRAVA_WEBHOOK_VERIFY_TOKEN are required")
    if settings.telegram_bot_token and settings.telegram_webhook_secret:
        steps.append(("Telegram", register_telegram_webhook))
    else:
        log.info("Skipping Telegram webhook registration: TELEGRAM_BOT_TOKEN and TELEGRAM_WEBHOOK_SECRET are required")
    return steps


async def ensure_webhooks_registered(settings: Settings) -> None:
    if not settings.public_base_url:
        log.info("Skipping webhook registration: PUBLIC_BASE_URL is not set")
        return
    if settings.app_env == "development":
        log.info("Skipping webhook registration: APP_ENV is development")
        return
    steps = _registration_steps(settings)
    if not steps:
        return
    attempt = 0
    while True:
        failed = False
        for name, register in steps:
            try:
                await asyncio.to_thread(register, settings)
            except Exception:
                failed = True
                log.warning("%s webhook registration failed", name, exc_info=True)
        if not failed:
            log.info("Webhook registration complete")
            return
        delay = RETRY_DELAYS_SECONDS[min(attempt, len(RETRY_DELAYS_SECONDS) - 1)]
        attempt += 1
        log.info(
            "Retrying webhook registration in %ss (Strava validates the callback URL with a hub.challenge request, so retries continue until the public URL is reachable)",
            delay,
        )
        await asyncio.sleep(delay)
