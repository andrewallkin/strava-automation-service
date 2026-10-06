from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"
    timezone: str = "UTC"

    postgres_db: str = "strava_automation"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    strava_client_id: str = ""
    strava_client_secret: str = ""
    strava_webhook_verify_token: str = ""
    strava_scopes: str = "activity:read,activity:write,profile:read_all"
    strava_allowed_athlete_id: int = 0  # 0 = no restriction (backward compat)

    telegram_bot_token: str = Field(
        default="",
        validation_alias=AliasChoices("TELEGRAM_BOT_TOKEN", "ACTIVITYADMIN_TELEGRAM_BOT_TOKEN"),
    )
    telegram_webhook_secret: str = Field(
        default="",
        validation_alias=AliasChoices("TELEGRAM_WEBHOOK_SECRET", "ACTIVITYADMIN_TELEGRAM_WEBHOOK_SECRET"),
    )
    telegram_allowed_user_id: int = Field(
        default=0,
        validation_alias=AliasChoices("TELEGRAM_ALLOWED_USER_ID", "ACTIVITYADMIN_TELEGRAM_ALLOWED_USER_ID"),
    )
    app_secret_key: str = ""
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_exp_minutes: int = 30
    jwt_cookie_name: str = "strava_auth"
    jwt_cookie_secure: bool = True
    jwt_cookie_samesite: str = "lax"
    jwt_cookie_domain: str = ""

    public_base_url: str = ""
    frontend_base_url: str = ""
    ui_port: int = 3001
    ui_api_base_url: str = "/api"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def _normalized_public_base_url(self) -> str:
        return self.public_base_url.rstrip("/")

    @property
    def telegram_webhook_url(self) -> str:
        if not self.public_base_url or not self.telegram_webhook_secret:
            return ""
        return f"{self._normalized_public_base_url}/api/telegram/activityadmin/webhook/{self.telegram_webhook_secret}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
