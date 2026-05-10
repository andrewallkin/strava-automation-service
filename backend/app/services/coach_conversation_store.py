from __future__ import annotations

import json
import logging
from typing import Any

from redis import Redis

DEFAULT_CONVERSATION_ID = "default"
log = logging.getLogger("coach.conversation")


def _default_store() -> dict[str, Any]:
    return {
        "conversations": {DEFAULT_CONVERSATION_ID: []},
        "last_active_conversation_id": DEFAULT_CONVERSATION_ID,
    }


def cap_by_history_items(history: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    if len(history) <= limit:
        return history
    return history[-limit:]


class CoachConversationStore:
    def __init__(self, redis_client: Redis) -> None:
        self._redis = redis_client

    @staticmethod
    def _key(user_id: int) -> str:
        return f"coach:conversation:user:{user_id}"

    def load_store(self, user_id: int) -> dict[str, Any]:
        log.info("Loading conversation store from Redis for user_id=%s", user_id)
        raw = self._redis.get(self._key(user_id))
        if not raw:
            log.info("No existing conversation store found for user_id=%s; creating default store", user_id)
            return _default_store()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            log.warning("Invalid conversation JSON for user_id=%s; resetting to default store", user_id)
            return _default_store()
        if not isinstance(parsed, dict):
            log.warning("Unexpected conversation payload for user_id=%s; resetting to default store", user_id)
            return _default_store()
        conversations = parsed.get("conversations")
        conversation_count = len(conversations) if isinstance(conversations, dict) else 0
        log.info(
            "Conversation store loaded for user_id=%s conversation_count=%s",
            user_id,
            conversation_count,
        )
        return parsed

    def save_store(self, user_id: int, store: dict[str, Any]) -> None:
        conversations = store.get("conversations")
        conversation_count = len(conversations) if isinstance(conversations, dict) else 0
        log.info(
            "Saving conversation store to Redis for user_id=%s conversation_count=%s",
            user_id,
            conversation_count,
        )
        self._redis.set(self._key(user_id), json.dumps(store, ensure_ascii=False))
        log.info("Conversation store persisted to Redis for user_id=%s", user_id)

    def get_history(self, user_id: int) -> list[dict[str, Any]]:
        store = self.load_store(user_id)
        conv_id = store.get("last_active_conversation_id") or DEFAULT_CONVERSATION_ID
        conversations = store.get("conversations")
        if not isinstance(conversations, dict):
            log.warning("Conversations payload missing for user_id=%s; returning empty history", user_id)
            return []
        history = conversations.get(conv_id)
        if not isinstance(history, list):
            log.info(
                "No history list found for user_id=%s conversation_id=%s; returning empty history",
                user_id,
                conv_id,
            )
            return []
        log.info(
            "Conversation history loaded for user_id=%s conversation_id=%s history_items=%s",
            user_id,
            conv_id,
            len(history),
        )
        return history

    def save_history(self, user_id: int, history: list[dict[str, Any]], history_item_limit: int) -> None:
        store = self.load_store(user_id)
        conv_id = store.get("last_active_conversation_id") or DEFAULT_CONVERSATION_ID
        log.info(
            "Saving conversation history for user_id=%s conversation_id=%s incoming_items=%s history_item_limit=%s",
            user_id,
            conv_id,
            len(history),
            history_item_limit,
        )
        capped = cap_by_history_items(history, history_item_limit)
        if len(capped) < len(history):
            log.info(
                "Conversation history truncated for user_id=%s conversation_id=%s removed_items=%s",
                user_id,
                conv_id,
                len(history) - len(capped),
            )
        else:
            log.info("Conversation history did not require truncation for user_id=%s", user_id)
        store["last_active_conversation_id"] = conv_id
        store["conversations"] = {conv_id: capped}
        self.save_store(user_id, store)

    def append_history(self, user_id: int, items: list[dict[str, Any]], history_item_limit: int) -> list[dict[str, Any]]:
        log.info("Appending conversation items for user_id=%s items_to_append=%s", user_id, len(items))
        history = list(self.get_history(user_id))
        history.extend(items)
        self.save_history(user_id, history, history_item_limit)
        updated = self.get_history(user_id)
        log.info("Conversation append completed for user_id=%s updated_history_items=%s", user_id, len(updated))
        return updated
