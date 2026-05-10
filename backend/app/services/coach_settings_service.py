from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User, UserCoachSettings

DEFAULT_AGENT_NAME = "Coach"
DEFAULT_AGENT_INSTRUCTIONS = ""
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"


def get_or_create_coach_settings(db: Session, user: User) -> UserCoachSettings:
    row = db.scalar(select(UserCoachSettings).where(UserCoachSettings.user_id == user.id))
    if row:
        return row
    now = datetime.now(timezone.utc)
    row = UserCoachSettings(
        user_id=user.id,
        vector_store_id=None,
        agent_name=DEFAULT_AGENT_NAME,
        agent_instructions=DEFAULT_AGENT_INSTRUCTIONS,
        openai_model=DEFAULT_OPENAI_MODEL,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_coach_settings(
    db: Session,
    user: User,
    *,
    vector_store_id: str | None | object = ...,
    agent_name: str | None | object = ...,
    agent_instructions: str | None | object = ...,
    openai_model: str | None | object = ...,
) -> UserCoachSettings:
    row = get_or_create_coach_settings(db, user)
    if vector_store_id is not ...:
        row.vector_store_id = (vector_store_id or None) if isinstance(vector_store_id, str) else None
    if agent_name is not ...:
        if not isinstance(agent_name, str):
            raise ValueError("agent_name must be a string")
        trimmed = agent_name.strip()
        if not trimmed:
            raise ValueError("agent_name is required")
        row.agent_name = trimmed
    if agent_instructions is not ...:
        if not isinstance(agent_instructions, str):
            raise ValueError("agent_instructions must be a string")
        row.agent_instructions = agent_instructions.strip()
    if openai_model is not ...:
        if not isinstance(openai_model, str):
            raise ValueError("openai_model must be a string")
        trimmed = openai_model.strip()
        if not trimmed:
            raise ValueError("openai_model is required")
        row.openai_model = trimmed

    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row
