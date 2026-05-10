from functools import lru_cache

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
    coach_telegram_bot_token: str = ""
    coach_telegram_webhook_secret: str = ""
    coach_telegram_allowed_user_id: int = 0
    coach_telegram_webhook_url: str = ""
    coach_conversation_history_user_turn_limit: int = 20
    coach_link_code_ttl_seconds: int = 600

    redis_url: str = "redis://redis:6379/0"
    mcp_server_url: str = ""
    strava_mcp_bearer: str = ""

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

    # OpenAI (vector store / file search UI — server-side only)
    openai_api_key: str = ""

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
