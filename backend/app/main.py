import asyncio
import logging
import logging.config
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.external_errors import ExternalAPIError


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
            "external":       {"handlers": ["console"], "level": log_level, "propagate": False},
        },
        "root": {"handlers": ["console"], "level": "WARNING"},
    })


_configure_logging()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.config import get_settings
    from app.services.webhook_registration import ensure_webhooks_registered

    registration_task = asyncio.create_task(ensure_webhooks_registered(get_settings()))
    try:
        yield
    finally:
        registration_task.cancel()
        with suppress(asyncio.CancelledError):
            await registration_task


app = FastAPI(title="Strava Automation Service", lifespan=lifespan)

from app.routers.auth import logout_router, router as auth_router
from app.routers.backfill_api import router as backfill_router
from app.routers.external import router as external_router
from app.routers.strava_webhook import router as strava_router
from app.routers.telegram_webhook import router as telegram_router
from app.routers.ui_api import router as ui_router

app.include_router(auth_router)
app.include_router(logout_router)
app.include_router(strava_router)
app.include_router(telegram_router)
app.include_router(ui_router)
app.include_router(backfill_router)
app.include_router(external_router)


@app.exception_handler(ExternalAPIError)
def external_api_error(_request, exc: ExternalAPIError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": exc.message}})


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
