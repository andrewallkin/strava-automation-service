from functools import lru_cache

from pydantic import Field
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

    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""
    telegram_allowed_user_id: int = 0
    telegram_webhook_url: str = ""

    app_secret_key: str = ""

    public_base_url: str = ""
    frontend_base_url: str = ""
    ui_port: int = 3001
    ui_api_base_url: str = "/api"

    tunnel_provider: str = "cloudflared"
    ngrok_authtoken: str = ""
    tunnel_domain: str = ""
    cloudflared_tunnel_token: str = Field(default="", alias="CLOUDFLARED_TUNNEL_TOKEN")

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
