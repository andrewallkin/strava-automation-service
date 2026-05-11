from __future__ import annotations

import secrets

from redis import Redis

from app.config import get_settings


class CoachLinkService:
    def __init__(self, redis_client: Redis) -> None:
        self._redis = redis_client
        self._settings = get_settings()

    @staticmethod
    def _code_key(code: str) -> str:
        return f"coach:link:code:{code}"

    def issue_code(self, user_id: int) -> tuple[str, int]:
        code = secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:10].upper()
        ttl = max(self._settings.coach_link_code_ttl_seconds, 60)
        self._redis.setex(self._code_key(code), ttl, str(user_id))
        return code, ttl

    def consume_code(self, code: str) -> int | None:
        key = self._code_key(code.strip().upper())
        raw_user_id = self._redis.get(key)
        if raw_user_id is None:
            return None
        self._redis.delete(key)
        try:
            return int(raw_user_id)
        except ValueError:
            return None
