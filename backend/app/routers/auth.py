from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import require_session
from app.models import User
from app.services.strava_service import StravaService

router = APIRouter(prefix="/api/auth/strava", tags=["auth"])


@router.get("/connect")
def connect() -> RedirectResponse:
    service = StravaService()
    return RedirectResponse(url=service.auth_url())


@router.get("/callback")
def callback(
    request: Request,
    code: str = Query(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    settings = get_settings()
    base_url = (settings.frontend_base_url or settings.public_base_url).rstrip("/") or "http://localhost"
    try:
        service = StravaService()
        service.exchange_code_for_token(db, code)
    except Exception as exc:  # pragma: no cover - passthrough error handling
        params = urlencode({"strava": "error", "message": str(exc)[:200]})
        return RedirectResponse(url=f"{base_url}/?{params}")

    request.session["connected"] = True
    return RedirectResponse(url=f"{base_url}/?strava=connected")


@router.delete("/disconnect")
def disconnect(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_session),
) -> dict:
    user = db.execute(select(User).limit(1)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="No user found")
    user.strava_athlete_id = None
    user.access_token = None
    user.refresh_token = None
    user.expires_at = None
    db.commit()
    request.session.clear()
    return {"disconnected": True}
