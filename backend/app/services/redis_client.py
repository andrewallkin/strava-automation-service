from __future__ import annotations

import logging
from functools import lru_cache

from redis import Redis

from app.config import get_settings

log = logging.getLogger("coach.redis")


@lru_cache
def get_redis_client() -> Redis:
    settings = get_settings()
    log.info("Connecting to Redis using configured URL")
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    log.info("Redis client initialized successfully")
    return client
