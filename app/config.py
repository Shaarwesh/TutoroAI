from pydantic_settings import BaseSettings


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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
