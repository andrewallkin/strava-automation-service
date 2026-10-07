from __future__ import annotations

import secrets
from datetime import datetime, timezone

import bcrypt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User

KEY_PREFIX = "sva_"
LOOKUP_LEN = 12


def create_external_api_key_material() -> tuple[str, str, str]:
    """Return (full_key, lookup_prefix, bcrypt_hash)."""
    full_key = f"{KEY_PREFIX}{secrets.token_urlsafe(32)}"
    lookup_prefix = full_key[:LOOKUP_LEN]
    key_hash = bcrypt.hashpw(full_key.encode(), bcrypt.gensalt()).decode()
    return full_key, lookup_prefix, key_hash


def assign_external_api_key(db: Session, user: User) -> str:
    full_key, lookup_prefix, key_hash = create_external_api_key_material()
    user.external_api_key_prefix = lookup_prefix
    user.external_api_key_hash = key_hash
    user.external_api_key_created_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()
    db.refresh(user)
    return full_key


def revoke_external_api_key(db: Session, user: User) -> None:
    user.external_api_key_prefix = None
    user.external_api_key_hash = None
    user.external_api_key_created_at = None
    db.add(user)
    db.commit()


def authenticate_external_api_key(db: Session, token: str) -> User | None:
    cleaned = token.strip()
    if not cleaned.startswith(KEY_PREFIX) or len(cleaned) < 20:
        return None
    if cleaned.startswith("sva_mcp_"):
        return None
    user = db.scalar(
        select(User).where(
            User.external_api_key_prefix == cleaned[:LOOKUP_LEN],
            User.external_api_key_hash.is_not(None),
        )
    )
    if user is None or not user.external_api_key_hash:
        return None
    if not bcrypt.checkpw(cleaned.encode(), user.external_api_key_hash.encode()):
        return None
    return user
