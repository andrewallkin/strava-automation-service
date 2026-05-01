from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User
from app.services.activity_service import upsert_gear

STRAVA_BASE_URL = "https://www.strava.com"
STRAVA_API_PREFIX = "/api/v3"
STRAVA_EXPLORER_METHODS = {"GET", "POST", "PUT", "DELETE"}


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
        resp = httpx.post(
            f"{STRAVA_BASE_URL}/oauth/token",
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

        resp = httpx.post(
            f"{STRAVA_BASE_URL}/oauth/token",
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

        resp = httpx.request(method, f"{STRAVA_BASE_URL}{path}", **request_kwargs)
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
                if key.lower().startswith("x-ratelimit") or key.lower() == "content-type"
            },
            "body": response_body,
        }

    def get_activity(self, db: Session, activity_id: int, user: User) -> dict:
        user = self.ensure_fresh_token(db, user)
        resp = httpx.get(
            f"{STRAVA_BASE_URL}/api/v3/activities/{activity_id}",
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
        resp = httpx.get(
            f"{STRAVA_BASE_URL}/api/v3/activities/{activity_id}",
            headers=self._headers(user.access_token or ""),
            params={"include_all_efforts": str(include_all_efforts).lower()},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def get_activity_laps(self, db: Session, activity_id: int, user: User) -> list[dict]:
        user = self.ensure_fresh_token(db, user)
        resp = httpx.get(
            f"{STRAVA_BASE_URL}/api/v3/activities/{activity_id}/laps",
            headers=self._headers(user.access_token or ""),
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    def get_activity_zones(self, db: Session, activity_id: int, user: User) -> list[dict] | None:
        user = self.ensure_fresh_token(db, user)
        resp = httpx.get(
            f"{STRAVA_BASE_URL}/api/v3/activities/{activity_id}/zones",
            headers=self._headers(user.access_token or ""),
            timeout=30,
        )
        if resp.status_code in {401, 403, 404}:
            return None
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    def get_athlete_zones(self, db: Session, user: User) -> dict | None:
        user = self.ensure_fresh_token(db, user)
        resp = httpx.get(
            f"{STRAVA_BASE_URL}/api/v3/athlete/zones",
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
        resp = httpx.get(
            f"{STRAVA_BASE_URL}/api/v3/activities/{activity_id}/streams",
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
        resp = httpx.put(
            f"{STRAVA_BASE_URL}/api/v3/activities/{activity_id}",
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
        resp = httpx.get(
            f"{STRAVA_BASE_URL}/api/v3/athlete/activities",
            headers=self._headers(user.access_token or ""),
            params={"per_page": per_page, "page": page},
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    def get_gear_detail(self, db: Session, user: User, gear_id: str) -> dict:
        user = self.ensure_fresh_token(db, user)
        resp = httpx.get(
            f"{STRAVA_BASE_URL}/api/v3/gear/{gear_id}",
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
            resp = httpx.get(
                f"{STRAVA_BASE_URL}/api/v3/athlete/activities",
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
            resp = httpx.get(
                f"{STRAVA_BASE_URL}/api/v3/athlete/activities",
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

    def sync_gear_cache(self, db: Session, user: User) -> list[dict]:
        user = self.ensure_fresh_token(db, user)
        resp = httpx.get(
            f"{STRAVA_BASE_URL}/api/v3/athlete",
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
        return shoes
