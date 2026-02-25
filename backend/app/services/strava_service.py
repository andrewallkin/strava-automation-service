from datetime import datetime, timezone

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User
from app.services.activity_service import upsert_gear

STRAVA_BASE_URL = "https://www.strava.com"


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
        if self.settings.strava_allowed_athlete_id and athlete_id != self.settings.strava_allowed_athlete_id:
            raise HTTPException(status_code=403, detail="Unauthorized athlete")
        user = self.get_or_create_user(db)
        user.strava_athlete_id = athlete_id
        user.access_token = data["access_token"]
        user.refresh_token = data["refresh_token"]
        user.expires_at = datetime.fromtimestamp(data["expires_at"], tz=timezone.utc)
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
            "&approval_prompt=force"
            "&scope="
            f"{scope}"
        )

    def _headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def get_activity(self, db: Session, activity_id: int, user: User) -> dict:
        user = self.ensure_fresh_token(db, user)
        resp = httpx.get(
            f"{STRAVA_BASE_URL}/api/v3/activities/{activity_id}",
            headers=self._headers(user.access_token or ""),
            timeout=20,
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
