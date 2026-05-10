from __future__ import annotations

import json
from typing import Any

from redis import Redis

DEFAULT_CONVERSATION_ID = "default"


def _default_store() -> dict[str, Any]:
    return {
        "conversations": {DEFAULT_CONVERSATION_ID: []},
        "last_active_conversation_id": DEFAULT_CONVERSATION_ID,
    }


def _is_user_input_item(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    return item.get("role") == "user"


def cap_by_user_turns(history: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    user_indexes = [idx for idx, item in enumerate(history) if _is_user_input_item(item)]
    if len(user_indexes) <= limit:
        return history
    first_keep_idx = user_indexes[-limit]
    return history[first_keep_idx:]


class CoachConversationStore:
    def __init__(self, redis_client: Redis) -> None:
        self._redis = redis_client

    @staticmethod
    def _key(user_id: int) -> str:
        return f"coach:conversation:user:{user_id}"

    def load_store(self, user_id: int) -> dict[str, Any]:
        raw = self._redis.get(self._key(user_id))
        if not raw:
            return _default_store()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return _default_store()
        if not isinstance(parsed, dict):
            return _default_store()
        return parsed

    def save_store(self, user_id: int, store: dict[str, Any]) -> None:
        self._redis.set(self._key(user_id), json.dumps(store, ensure_ascii=False))

    def get_history(self, user_id: int) -> list[dict[str, Any]]:
        store = self.load_store(user_id)
        conv_id = store.get("last_active_conversation_id") or DEFAULT_CONVERSATION_ID
        conversations = store.get("conversations")
        if not isinstance(conversations, dict):
            return []
        history = conversations.get(conv_id)
        if not isinstance(history, list):
            return []
        return history

    def save_history(self, user_id: int, history: list[dict[str, Any]], user_turn_limit: int) -> None:
        store = self.load_store(user_id)
        conv_id = store.get("last_active_conversation_id") or DEFAULT_CONVERSATION_ID
        capped = cap_by_user_turns(history, user_turn_limit)
        store["last_active_conversation_id"] = conv_id
        store["conversations"] = {conv_id: capped}
        self.save_store(user_id, store)

    def append_history(self, user_id: int, items: list[dict[str, Any]], user_turn_limit: int) -> list[dict[str, Any]]:
        history = list(self.get_history(user_id))
        history.extend(items)
        self.save_history(user_id, history, user_turn_limit)
        return self.get_history(user_id)
