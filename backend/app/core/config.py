from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    MONGODB_URL: str
    DATABASE_NAME: str = "fleetpulse_db"
    FRONTEND_URL: str = "http://localhost:5173"
    JWT_SECRET_KEY: str
    COOKIE_SECURE: bool = False

    # SMTP email configuration
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""

    # F3 - Calendarific
    CALENDARIFIC_API_KEY: str = ""
    CALENDARIFIC_COUNTRY: str = "BD"

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()