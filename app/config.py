from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    # Twilio
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_whatsapp_number: str

    # Groq
    groq_api_key: str

    # PostgreSQL
    database_url: str

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Google Calendar
    google_calendar_id: str
    google_service_account_file: str = "app/credentials/google_service_account.json"

    # App
    app_env: str = "development"
    secret_key: str = "change_me"
    port: int = 8000
    admin_whatsapp_number: str = ""  # e.g. whatsapp:+60123456789 — tuition centre owner's number

    @field_validator("database_url")
    @classmethod
    def fix_asyncpg_driver(cls, v: str) -> str:
        """Railway/Heroku-style URLs come as postgresql:// — convert to asyncpg driver format."""
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
