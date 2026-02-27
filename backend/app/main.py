from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.routers.auth import router as auth_router
from app.routers.strava_webhook import router as strava_router
from app.routers.telegram_webhook import router as telegram_router
from app.routers.ui_api import router as ui_router

app = FastAPI(title="Strava Automation Service")

settings = get_settings()
if not settings.app_secret_key:
    raise ValueError("APP_SECRET_KEY must be set for session authentication")
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.app_secret_key,
    max_age=300,  # 5 minutes (for testing)
    session_cookie="strava_session",
    same_site="lax",
)

app.include_router(auth_router)
app.include_router(strava_router)
app.include_router(telegram_router)
app.include_router(ui_router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
