from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache
import os


class Settings(BaseSettings):
    database_url: str = "sqlite:///./health_transform.db"
    telegram_bot_token: str = ""
    telegram_bot_username: str = ""
    # AI providers — use whichever key is available
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    openrouter_api_key: str = ""
    webapp_url: str = ""
    upload_dir: str = "./uploads/photos"
    host: str = "0.0.0.0"
    port: int = 8000
    usda_api_key: str = ""
    scheduler_enabled: bool = True
    scheduler_weekly_hour: int = 21
    reminder_check_interval_minutes: int = 1
    sentry_dsn: str = ""
    # Auth / environment
    environment: str = "development"  # set to "production" in prod .env
    jwt_secret: str = ""              # HMAC secret for account (email/password) JWTs; required in prod
    encryption_key: str = ""          # Fernet key for app-level encryption of sensitive fields; required in prod
    dev_auth_enabled: bool = True     # set False in prod; auto-disabled when telegram_bot_token is set
    feedback_channel_id: str = ""     # Telegram chat_id to receive feedback messages
    feedback_admin_chat_id: str = ""  # Telegram chat_id for admin feedback forwarding (group or person)
    feedback_bot_token: str = ""      # Optional: dedicated Telegram bot for sending feedback. Falls back to telegram_bot_token if empty.

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @field_validator("webapp_url", mode="before")
    @classmethod
    def strip_webapp_url(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v


@lru_cache()
def get_settings() -> Settings:
    return Settings()
