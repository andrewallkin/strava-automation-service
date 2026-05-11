"""Store and resolve OpenAI API keys: Fernet at rest, per user."""

from __future__ import annotations

import base64
import hashlib
import logging
from datetime import datetime, timezone

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User, UserOpenAiApiKey

log = logging.getLogger(__name__)


def _mask_openai_api_key(plain: str) -> str:
    s = plain.strip()
    if not s:
        return ""
    if len(s) <= 11:
        tail = s[-4:] if len(s) >= 4 else "••••"
        return f"…{tail}"
    return f"{s[:7]}…{s[-4:]}"


def _fernet() -> Fernet:
    settings = get_settings()
    secret = (settings.jwt_secret or settings.app_secret_key or "").strip()
    if not secret:
        raise ValueError(
            "APP_SECRET_KEY (or JWT_SECRET) is required to encrypt OpenAI credentials"
        )
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def encrypt_api_key(plain: str) -> str:
    return _fernet().encrypt(plain.strip().encode()).decode()


def decrypt_api_key(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        log.warning("OpenAI credential decrypt failed (wrong APP_SECRET_KEY/JWT_SECRET?)")
        raise ValueError("Stored OpenAI key could not be decrypted; save it again in Settings") from None


def get_openai_api_key_for_user(db: Session, user: User) -> str | None:
    row = db.scalar(select(UserOpenAiApiKey).where(UserOpenAiApiKey.user_id == user.id))
    if row:
        try:
            return decrypt_api_key(row.ciphertext).strip()
        except ValueError:
            return None
    env_key = get_settings().openai_api_key.strip()
    if env_key:
        return env_key
    return None


def save_openai_api_key(db: Session, user: User, plain: str) -> UserOpenAiApiKey:
    trimmed = plain.strip()
    if not trimmed:
        raise ValueError("API key is required")
    if not (trimmed.startswith("sk-") and len(trimmed) > 10):
        raise ValueError("API key must look like an OpenAI secret key (starts with sk-)")

    ct = encrypt_api_key(trimmed)
    prefix = _mask_openai_api_key(trimmed)
    now = datetime.now(timezone.utc)
    row = db.scalar(select(UserOpenAiApiKey).where(UserOpenAiApiKey.user_id == user.id))
    if row:
        row.ciphertext = ct
        row.key_prefix = prefix
        row.updated_at = now
    else:
        row = UserOpenAiApiKey(
            user_id=user.id,
            ciphertext=ct,
            key_prefix=prefix,
            updated_at=now,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


def delete_openai_api_key(db: Session, user: User) -> bool:
    row = db.scalar(select(UserOpenAiApiKey).where(UserOpenAiApiKey.user_id == user.id))
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


def get_openai_credential_status(db: Session, user: User) -> tuple[bool, str | None, datetime | None]:
    row = db.scalar(select(UserOpenAiApiKey).where(UserOpenAiApiKey.user_id == user.id))
    if not row:
        return False, None, None
    return True, row.key_prefix, row.updated_at
