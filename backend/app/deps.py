from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.services.jwt_service import AUTH_COOKIE_NAME, JwtService


def require_jwt_payload(request: Request) -> dict:
    """Validate JWT from auth cookie and return payload."""
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Session expired or not authenticated")
    service = JwtService()
    return service.decode_token(token)


def require_jwt_user(
    payload: dict = Depends(require_jwt_payload),
    db: Session = Depends(get_db),
) -> User:
    sub = payload.get("sub")
    try:
        user_id = int(sub)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid authentication token") from exc

    user = db.scalar(select(User).where(User.id == user_id).limit(1))
    if not user:
        raise HTTPException(status_code=401, detail="Authenticated user not found")
    return user
