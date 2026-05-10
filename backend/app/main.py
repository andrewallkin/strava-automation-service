import logging
import logging.config

from fastapi import FastAPI


def _configure_logging() -> None:
    from app.config import get_settings
    log_level = get_settings().log_level.upper()
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s  %(levelname)-8s [%(name)-14s] %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "standard",
            },
        },
        "loggers": {
            "uvicorn":        {"handlers": ["console"], "level": log_level, "propagate": False},
            "uvicorn.error":  {"handlers": ["console"], "level": log_level, "propagate": False},
            "uvicorn.access": {"handlers": ["console"], "level": log_level, "propagate": False},
            "webhook":        {"handlers": ["console"], "level": log_level, "propagate": False},
            "processor":      {"handlers": ["console"], "level": log_level, "propagate": False},
            "telegram":       {"handlers": ["console"], "level": log_level, "propagate": False},
            "auth":           {"handlers": ["console"], "level": log_level, "propagate": False},
            "db":             {"handlers": ["console"], "level": log_level, "propagate": False},
            "ingestion":      {"handlers": ["console"], "level": log_level, "propagate": False},
            "coach":          {"handlers": ["console"], "level": log_level, "propagate": False},
        },
        "root": {"handlers": ["console"], "level": "WARNING"},
    })


_configure_logging()

app = FastAPI(title="Strava Automation Service")

from app.routers.auth import logout_router, router as auth_router
from app.routers.backfill_api import router as backfill_router
from app.routers.telegram_coach_webhook import router as telegram_coach_router
from app.routers.strava_webhook import router as strava_router
from app.routers.telegram_webhook import router as telegram_router
from app.routers.ui_api import router as ui_router
from app.routers.vector_stores_ui import router as vector_stores_ui_router

app.include_router(auth_router)
app.include_router(logout_router)
app.include_router(strava_router)
app.include_router(telegram_router)
app.include_router(telegram_coach_router)
app.include_router(ui_router)
app.include_router(vector_stores_ui_router)
app.include_router(backfill_router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
