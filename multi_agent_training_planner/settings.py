from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_PKG_ROOT = Path(__file__).resolve().parent
_REPO_ROOT = _PKG_ROOT.parent


def _env_files() -> tuple[str, ...]:
    candidates: list[Path] = []
    for base in (_REPO_ROOT, _PKG_ROOT, Path.cwd()):
        p = base / ".env"
        if p.is_file() and p not in candidates:
            candidates.append(p)
    return tuple(str(p) for p in candidates)


class PlannerSettings(BaseSettings):
    """Loads the same env vars the backend uses for planner-relevant settings (no backend code)."""

    model_config = SettingsConfigDict(
        env_file=_env_files(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""
    timezone: str = "UTC"
    mcp_server_url: str = ""
    strava_mcp_bearer: str = ""


@lru_cache
def get_planner_settings() -> PlannerSettings:
    return PlannerSettings()
