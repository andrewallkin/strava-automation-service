import logging
import threading
import time
from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator
from urllib.parse import parse_qs, urlsplit

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Gear, User
from app.services.activity_service import upsert_gear

log = logging.getLogger("strava")

STRAVA_BASE_URL = "https://www.strava.com"
STRAVA_API_PREFIX = "/api/v3"
STRAVA_EXPLORER_METHODS = {"GET", "POST", "PUT", "DELETE"}
STRAVA_DEFAULT_READ_15_MIN_LIMIT = 100
STRAVA_DEFAULT_READ_DAILY_LIMIT = 1000
STRAVA_RATE_LIMIT_RETRY_ATTEMPTS = 1


@dataclass(frozen=True)
class StravaRateLimitWait:
    reason: str
    wait_until: datetime
    wait_seconds: float


RateLimitWaitHandler = Callable[[StravaRateLimitWait | None], None]
_RATE_LIMIT_WAIT_HANDLER: ContextVar[RateLimitWaitHandler | None] = ContextVar(
    "strava_rate_limit_wait_handler",
    default=None,
)


@contextmanager
def strava_rate_limit_wait_handler(handler: RateLimitWaitHandler) -> Iterator[None]:
    token: Token[RateLimitWaitHandler | None] = _RATE_LIMIT_WAIT_HANDLER.set(handler)
    try:
        yield
    finally:
        _RATE_LIMIT_WAIT_HANDLER.reset(token)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StravaRateLimiter:
    def __init__(
        self,
        clock: Callable[[], datetime] = _utc_now,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.clock = clock
        self.sleeper = sleeper
        self._lock = threading.Lock()
        self._pause_until: datetime | None = None

    def wait_before_request(self, method: str, url: str) -> None:
        if not self._is_read_request(method, url):
            return
        wait_seconds = 0.0
        wait_until: datetime | None = None
        with self._lock:
            now = self._now()
            if self._pause_until and self._pause_until > now:
                wait_until = self._pause_until
                wait_seconds = (self._pause_until - now).total_seconds()
        if wait_seconds > 0:
            self._notify_waiting("read rate limit", wait_until, wait_seconds)
            self.sleeper(wait_seconds)
            self._notify_resumed()

    def update_from_response(self, method: str, url: str, response: httpx.Response) -> None:
        if not self._is_read_request(method, url):
            return
        limit = self._read_limit(response)
        usage = self._read_usage(response)
        if not usage:
            return

        pause_until: datetime | None = None
        now = self._now()
        short_limit, daily_limit = limit
        short_usage, daily_usage = usage
        if short_usage >= short_limit:
            pause_until = self._next_15_min_reset(now)
        if daily_usage >= daily_limit:
            daily_reset = self._next_daily_reset(now)
            pause_until = max(pause_until, daily_reset) if pause_until else daily_reset
        if pause_until:
            with self._lock:
                self._pause_until = max(self._pause_until, pause_until) if self._pause_until else pause_until

    def wait_after_rate_limit(self, method: str, url: str, response: httpx.Response) -> None:
        if not self._is_read_request(method, url):
            return

        retry_after = self._retry_after_seconds(response)
        self.update_from_response(method, url, response)

        wait_until: datetime | None = None
        now = self._now()
        with self._lock:
            wait_until = self._pause_until
            if retry_after is not None:
                retry_until = now + timedelta(seconds=retry_after)
                wait_until = max(wait_until, retry_until) if wait_until else retry_until
                self._pause_until = wait_until
            elif not wait_until or wait_until <= now:
                wait_until = self._next_15_min_reset(now)
                self._pause_until = wait_until

        wait_seconds = (wait_until - now).total_seconds() if wait_until and wait_until > now else 0.0
        if wait_seconds > 0:
            self._notify_waiting("read rate limit", wait_until, wait_seconds)
            self.sleeper(wait_seconds)
            self._notify_resumed()

    def _read_limit(self, response: httpx.Response) -> tuple[int, int]:
        read_limit = self._header_pair(response, "x-readratelimit-limit")
        if read_limit:
            return read_limit
        overall_limit = self._header_pair(response, "x-ratelimit-limit")
        if overall_limit:
            return (
                min(overall_limit[0], STRAVA_DEFAULT_READ_15_MIN_LIMIT),
                min(overall_limit[1], STRAVA_DEFAULT_READ_DAILY_LIMIT),
            )
        return STRAVA_DEFAULT_READ_15_MIN_LIMIT, STRAVA_DEFAULT_READ_DAILY_LIMIT

    def _read_usage(self, response: httpx.Response) -> tuple[int, int] | None:
        return self._header_pair(response, "x-readratelimit-usage") or self._header_pair(
            response, "x-ratelimit-usage"
        )

    def _header_pair(self, response: httpx.Response, name: str) -> tuple[int, int] | None:
        raw_value = None
        for key, value in response.headers.items():
            if key.lower() == name:
                raw_value = value
                break
        if raw_value is None:
            return None
        parts = [part.strip() for part in raw_value.split(",", maxsplit=1)]
        if len(parts) != 2:
            return None
        try:
            return int(parts[0]), int(parts[1])
        except ValueError:
            return None

    def _retry_after_seconds(self, response: httpx.Response) -> int | None:
        retry_after = response.headers.get("retry-after")
        if not retry_after:
            return None
        try:
            return max(int(retry_after), 0)
        except ValueError:
            return None

    def _is_read_request(self, method: str, url: str) -> bool:
        parts = urlsplit(url)
        return method.upper() == "GET" and parts.path.startswith(STRAVA_API_PREFIX)

    def _now(self) -> datetime:
        now = self.clock()
        if now.tzinfo is None:
            return now.replace(tzinfo=timezone.utc)
        return now.astimezone(timezone.utc)

    def _next_15_min_reset(self, now: datetime) -> datetime:
        epoch = int(now.timestamp())
        return datetime.fromtimestamp(((epoch // 900) + 1) * 900, tz=timezone.utc)

    def _next_daily_reset(self, now: datetime) -> datetime:
        next_day = (now + timedelta(days=1)).date()
        return datetime.combine(next_day, datetime.min.time(), tzinfo=timezone.utc)

    def _notify_waiting(
        self,
        reason: str,
        wait_until: datetime | None,
        wait_seconds: float,
    ) -> None:
        handler = _RATE_LIMIT_WAIT_HANDLER.get()
        if handler and wait_until:
            handler(StravaRateLimitWait(reason=reason, wait_until=wait_until, wait_seconds=wait_seconds))

    def _notify_resumed(self) -> None:
        handler = _RATE_LIMIT_WAIT_HANDLER.get()
        if handler:
            handler(None)


_STRAVA_RATE_LIMITER = StravaRateLimiter()


class StravaService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def get_or_create_user(self, db: Session) -> User:
        user = db.scalar(select(User).limit(1))
        if user:
            return user
        user = User()
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def exchange_code_for_token(self, db: Session, code: str) -> User:
        if not self.settings.strava_allowed_athlete_id:
            raise HTTPException(
                status_code=500,
                detail="STRAVA_ALLOWED_ATHLETE_ID must be configured for single-user mode",
            )
        resp = self._post(
            "/oauth/token",
            data={
                "client_id": self.settings.strava_client_id,
                "client_secret": self.settings.strava_client_secret,
                "code": code,
                "grant_type": "authorization_code",
            },
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        athlete_id = data.get("athlete", {}).get("id")
        if athlete_id != self.settings.strava_allowed_athlete_id:
            raise HTTPException(status_code=403, detail="Unauthorized athlete")
        user = self.get_or_create_user(db)
        user.strava_athlete_id = athlete_id
        user.access_token = data["access_token"]
        user.refresh_token = data["refresh_token"]
        user.expires_at = datetime.fromtimestamp(data["expires_at"], tz=timezone.utc)
        athlete = data.get("athlete", {})
        user.athlete_name = (
            f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip() or None
        )
        user.athlete_profile_url = athlete.get("profile")
        db.commit()
        db.refresh(user)
        return user

    def ensure_fresh_token(self, db: Session, user: User) -> User:
        if not user.expires_at or not user.refresh_token:
            return user
        now = datetime.now(timezone.utc)
        expires_at = user.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if now < expires_at:
            return user

        resp = self._post(
            "/oauth/token",
            data={
                "client_id": self.settings.strava_client_id,
                "client_secret": self.settings.strava_client_secret,
                "grant_type": "refresh_token",
                "refresh_token": user.refresh_token,
            },
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        user.access_token = data["access_token"]
        user.refresh_token = data["refresh_token"]
        user.expires_at = datetime.fromtimestamp(data["expires_at"], tz=timezone.utc)
        db.commit()
        db.refresh(user)
        return user

    def auth_url(self) -> str:
        scope = self.settings.strava_scopes
        redirect_uri = self.settings.public_base_url.rstrip("/") + "/api/auth/strava/callback"
        return (
            f"{STRAVA_BASE_URL}/oauth/authorize"
            f"?client_id={self.settings.strava_client_id}"
            "&response_type=code"
            f"&redirect_uri={redirect_uri}"
            "&approval_prompt=auto"
            "&scope="
            f"{scope}"
        )

    def _headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        method = method.upper()
        for attempt in range(STRAVA_RATE_LIMIT_RETRY_ATTEMPTS + 1):
            _STRAVA_RATE_LIMITER.wait_before_request(method, url)
            resp = httpx.request(method, url, **kwargs)
            if resp.status_code != 429 or attempt >= STRAVA_RATE_LIMIT_RETRY_ATTEMPTS:
                _STRAVA_RATE_LIMITER.update_from_response(method, url, resp)
                return resp
            _STRAVA_RATE_LIMITER.wait_after_rate_limit(method, url, resp)
        return resp

    def _get(self, path: str, **kwargs: Any) -> httpx.Response:
        return self._request("GET", f"{STRAVA_BASE_URL}{path}", **kwargs)

    def _post(self, path: str, **kwargs: Any) -> httpx.Response:
        return self._request("POST", f"{STRAVA_BASE_URL}{path}", **kwargs)

    def _put(self, path: str, **kwargs: Any) -> httpx.Response:
        return self._request("PUT", f"{STRAVA_BASE_URL}{path}", **kwargs)

    def explore_api(
        self,
        db: Session,
        user: User,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        body: Any | None = None,
        body_encoding: str = "json",
    ) -> dict:
        method = method.upper()
        if method not in STRAVA_EXPLORER_METHODS:
            raise HTTPException(status_code=400, detail="Unsupported Strava API method")

        parts = urlsplit(endpoint.strip())
        if parts.scheme or parts.netloc:
            raise HTTPException(status_code=400, detail="Use a Strava API path, not a full URL")

        path = parts.path or ""
        if not path.startswith("/"):
            path = f"/{path}"
        if ".." in path.split("/"):
            raise HTTPException(status_code=400, detail="Endpoint cannot contain path traversal")
        if not path.startswith(STRAVA_API_PREFIX):
            path = f"{STRAVA_API_PREFIX}{path}"
        if not path.startswith(f"{STRAVA_API_PREFIX}/") and path != STRAVA_API_PREFIX:
            raise HTTPException(status_code=400, detail="Endpoint must stay within /api/v3")

        query_params: dict[str, Any] = {}
        for key, values in parse_qs(parts.query, keep_blank_values=True).items():
            query_params[key] = values if len(values) > 1 else values[0]
        if params:
            query_params.update(params)

        user = self.ensure_fresh_token(db, user)
        request_kwargs: dict[str, Any] = {
            "headers": self._headers(user.access_token or ""),
            "params": query_params or None,
            "timeout": 30,
        }
        if method not in {"GET", "DELETE"} and body is not None:
            if body_encoding == "form":
                request_kwargs["data"] = body
            else:
                request_kwargs["json"] = body

        resp = self._request(method, f"{STRAVA_BASE_URL}{path}", **request_kwargs)
        content_type = resp.headers.get("content-type", "")
        if resp.content and "application/json" in content_type:
            response_body: Any = resp.json()
        elif resp.content:
            response_body = resp.text
        else:
            response_body = None

        return {
            "method": method,
            "endpoint": path,
            "url": str(resp.request.url),
            "status_code": resp.status_code,
            "headers": {
                key: value
                for key, value in resp.headers.items()
                if key.lower().startswith(("x-ratelimit", "x-readratelimit"))
                or key.lower() == "content-type"
            },
            "body": response_body,
        }

    def get_activity(self, db: Session, activity_id: int, user: User) -> dict:
        user = self.ensure_fresh_token(db, user)
        resp = self._get(
            f"/api/v3/activities/{activity_id}",
            headers=self._headers(user.access_token or ""),
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()

    def get_activity_detail(
        self,
        db: Session,
        activity_id: int,
        user: User,
        include_all_efforts: bool = True,
    ) -> dict:
        user = self.ensure_fresh_token(db, user)
        resp = self._get(
            f"/api/v3/activities/{activity_id}",
            headers=self._headers(user.access_token or ""),
            params={"include_all_efforts": str(include_all_efforts).lower()},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def get_activity_laps(self, db: Session, activity_id: int, user: User) -> list[dict]:
        user = self.ensure_fresh_token(db, user)
        resp = self._get(
            f"/api/v3/activities/{activity_id}/laps",
            headers=self._headers(user.access_token or ""),
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    def get_activity_zones(self, db: Session, activity_id: int, user: User) -> list[dict] | None:
        user = self.ensure_fresh_token(db, user)
        resp = self._get(
            f"/api/v3/activities/{activity_id}/zones",
            headers=self._headers(user.access_token or ""),
            timeout=30,
        )
        if resp.status_code in {401, 403, 404}:
            return None
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    def get_athlete_zones(self, db: Session, user: User) -> dict | None:
        user = self.ensure_fresh_token(db, user)
        resp = self._get(
            "/api/v3/athlete/zones",
            headers=self._headers(user.access_token or ""),
            timeout=30,
        )
        if resp.status_code in {401, 403, 404}:
            return None
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    def get_activity_streams(
        self,
        db: Session,
        activity_id: int,
        user: User,
        keys: list[str],
        key_by_type: bool = True,
    ) -> dict:
        user = self.ensure_fresh_token(db, user)
        resp = self._get(
            f"/api/v3/activities/{activity_id}/streams",
            headers=self._headers(user.access_token or ""),
            params={
                "keys": ",".join(keys),
                "key_by_type": str(key_by_type).lower(),
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def update_activity(self, db: Session, activity_id: int, payload: dict, user: User) -> dict:
        user = self.ensure_fresh_token(db, user)
        resp = self._put(
            f"/api/v3/activities/{activity_id}",
            data=payload,
            headers=self._headers(user.access_token or ""),
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()

    def get_athlete_activities(
        self, db: Session, user: User, per_page: int = 30, page: int = 1
    ) -> list[dict]:
        user = self.ensure_fresh_token(db, user)
        resp = self._get(
            "/api/v3/athlete/activities",
            headers=self._headers(user.access_token or ""),
            params={"per_page": per_page, "page": page},
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    def get_gear_detail(self, db: Session, user: User, gear_id: str) -> dict:
        user = self.ensure_fresh_token(db, user)
        resp = self._get(
            f"/api/v3/gear/{gear_id}",
            headers=self._headers(user.access_token or ""),
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()

    def get_activities_since(
        self, db: Session, user: User, after_epoch: int, max_pages: int = 10
    ) -> list[dict]:
        user = self.ensure_fresh_token(db, user)
        results: list[dict] = []
        for page in range(1, max_pages + 1):
            resp = self._get(
                "/api/v3/athlete/activities",
                headers=self._headers(user.access_token or ""),
                params={"after": after_epoch, "per_page": 200, "page": page},
                timeout=30,
            )
            resp.raise_for_status()
            batch: list[dict] = resp.json()
            results.extend(batch)
            if len(batch) < 200:
                break
        return results

    def get_athlete_activities_between(
        self,
        db: Session,
        user: User,
        after_epoch: int,
        before_epoch: int,
        max_pages: int | None = None,
    ) -> list[dict]:
        user = self.ensure_fresh_token(db, user)
        results: list[dict] = []
        page = 1
        while max_pages is None or page <= max_pages:
            resp = self._get(
                "/api/v3/athlete/activities",
                headers=self._headers(user.access_token or ""),
                params={
                    "after": after_epoch,
                    "before": before_epoch,
                    "per_page": 200,
                    "page": page,
                },
                timeout=30,
            )
            resp.raise_for_status()
            batch: list[dict] = resp.json()
            results.extend(batch)
            if len(batch) < 200:
                break
            page += 1
        return results

    def get_athlete_profile(self, db: Session, user: User) -> dict:
        user = self.ensure_fresh_token(db, user)
        resp = self._get(
            "/api/v3/athlete",
            headers=self._headers(user.access_token or ""),
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()

    def get_athlete_stats(self, db: Session, user: User, athlete_id: int) -> dict:
        user = self.ensure_fresh_token(db, user)
        resp = self._get(
            f"/api/v3/athletes/{athlete_id}/stats",
            headers=self._headers(user.access_token or ""),
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()

    def sync_gear_cache(self, db: Session, user: User) -> list[dict]:
        user = self.ensure_fresh_token(db, user)
        resp = self._get(
            "/api/v3/athlete",
            headers=self._headers(user.access_token or ""),
            timeout=20,
        )
        resp.raise_for_status()
        athlete = resp.json()
        shoes = athlete.get("shoes", [])
        for idx, shoe in enumerate(shoes):
            upsert_gear(
                db,
                strava_gear_id=shoe["id"],
                name=shoe.get("name", shoe["id"]),
                is_default=idx == 0,
            )
        # upsert_gear does not populate distance/details; ingestion only syncs gear when an activity
        # carries gear_id. Fill missing rows here so MCP / DB reports match Strava shoe totals.
        from app.services.strava_profile_service import sync_gear_detail

        for shoe in shoes:
            gear_id = shoe["id"]
            row = db.scalar(select(Gear).where(Gear.strava_gear_id == gear_id))
            if row is not None and row.fetched_at is None:
                try:
                    sync_gear_detail(db, user, gear_id, self)
                except Exception as exc:
                    log.warning("Gear detail sync failed | gear_id=%s error=%s", gear_id, exc)
        return shoes
