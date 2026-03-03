from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import require_jwt_user
from app.models import User
from app.services.jwt_service import JwtService
from app.services.strava_service import StravaService

router = APIRouter(prefix="/api/auth/strava", tags=["auth"])
logout_router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/connect")
def connect() -> RedirectResponse:
    service = StravaService()
    return RedirectResponse(url=service.auth_url())


@router.get("/callback")
def callback(
    code: str = Query(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    settings = get_settings()
    base_url = (settings.frontend_base_url or settings.public_base_url).rstrip("/") or "http://localhost"
    try:
        service = StravaService()
        user = service.exchange_code_for_token(db, code)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - passthrough error handling
        params = urlencode({"strava": "error", "message": str(exc)[:200]})
        return RedirectResponse(url=f"{base_url}/?{params}")

    response = RedirectResponse(url=f"{base_url}/?strava=connected")
    jwt_service = JwtService()
    jwt_service.set_auth_cookie(response, jwt_service.issue_token(user))
    return response


@logout_router.post("/logout")
def logout(response: Response) -> dict:
    jwt_service = JwtService()
    jwt_service.clear_auth_cookie(response)
    return {"logged_out": True}


@router.delete("/disconnect")
def disconnect_strava(
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(require_jwt_user),
) -> dict:
    user.strava_athlete_id = None
    user.access_token = None
    user.refresh_token = None
    user.expires_at = None
    db.commit()
    jwt_service = JwtService()
    jwt_service.clear_auth_cookie(response)
    return {"disconnected": True}
