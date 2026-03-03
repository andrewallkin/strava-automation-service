from fastapi import FastAPI

from app.routers.auth import logout_router, router as auth_router
from app.routers.strava_webhook import router as strava_router
from app.routers.telegram_webhook import router as telegram_router
from app.routers.ui_api import router as ui_router

app = FastAPI(title="Strava Automation Service")

app.include_router(auth_router)
app.include_router(logout_router)
app.include_router(strava_router)
app.include_router(telegram_router)
app.include_router(ui_router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
