from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.models import McpApiKey, User

KEY_PREFIX = "sva_mcp_"


@dataclass(frozen=True)
class CreatedMcpApiKey:
    raw_key: str
    row: McpApiKey


def hash_mcp_api_key(raw_key: str) -> str:
    settings = get_settings()
    secret = settings.jwt_secret or settings.app_secret_key or "dev-mcp-api-key-secret"
    return hmac.new(secret.encode("utf-8"), raw_key.encode("utf-8"), hashlib.sha256).hexdigest()


def create_mcp_api_key(db: Session, user: User, name: str | None = None) -> CreatedMcpApiKey:
    raw_key = f"{KEY_PREFIX}{secrets.token_urlsafe(32)}"
    row = McpApiKey(
        user_id=user.id,
        name=name,
        key_hash=hash_mcp_api_key(raw_key),
        key_prefix=raw_key[:16],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return CreatedMcpApiKey(raw_key=raw_key, row=row)


def list_mcp_api_keys(db: Session, user: User) -> list[McpApiKey]:
    return list(
        db.scalars(
            select(McpApiKey)
            .where(McpApiKey.user_id == user.id)
            .order_by(McpApiKey.created_at.desc())
        ).all()
    )


def revoke_mcp_api_key(db: Session, user: User, key_id: int) -> bool:
    row = db.scalar(
        select(McpApiKey)
        .where(McpApiKey.id == key_id, McpApiKey.user_id == user.id, McpApiKey.revoked_at.is_(None))
        .limit(1)
    )
    if not row:
        return False
    row.revoked_at = datetime.now(UTC)
    db.commit()
    return True


def authenticate_mcp_api_key(db: Session, raw_key: str) -> User | None:
    key_hash = hash_mcp_api_key(raw_key)
    row = db.scalar(
        select(McpApiKey)
        .where(McpApiKey.key_hash == key_hash, McpApiKey.revoked_at.is_(None))
        .limit(1)
    )
    if not row:
        return None

    user = db.scalar(select(User).where(User.id == row.user_id).limit(1))
    if not user or not user.strava_athlete_id:
        return None

    row.last_used_at = datetime.now(UTC)
    db.flush()
    db.expunge(user)
    db.commit()
    return user


def is_valid_mcp_api_key(raw_key: str) -> bool:
    with SessionLocal() as db:
        row = db.scalar(
            select(McpApiKey)
            .where(McpApiKey.key_hash == hash_mcp_api_key(raw_key), McpApiKey.revoked_at.is_(None))
            .limit(1)
        )
        if not row:
            return False
        user = db.scalar(select(User).where(User.id == row.user_id).limit(1))
        return bool(user and user.strava_athlete_id)
