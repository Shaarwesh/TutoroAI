
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Twilio is optional for local demonstrations.
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_number: str = ""

    # AI
    groq_api_key: str = ""

    # Database
    database_url: str
    redis_url: str = "redis://localhost:6379"

    # Google Calendar
    google_calendar_id: str = ""
    google_service_account_file: str = (
        "app/credentials/google_service_account.json"
    )

    # Application
    app_env: str = "development"
    demo_mode: bool = False
    secret_key: str = "change_me"
    port: int = 8000
    sentry_dsn: str = ""

    # Admin
    admin_initial_password: str = ""
    admin_recovery_email: str = ""
    admin_whatsapp_number: str = ""

    @field_validator("database_url")
    @classmethod
    def fix_asyncpg_driver(cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return value.replace(
                "postgresql://",
                "postgresql+asyncpg://",
                1,
            )
        if value.startswith("postgres://"):
            return value.replace(
                "postgres://",
                "postgresql+asyncpg://",
                1,
            )
        return value


settings = Settings()
