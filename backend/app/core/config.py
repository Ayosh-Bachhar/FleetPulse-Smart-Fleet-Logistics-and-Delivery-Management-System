from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    MONGODB_URL: str
    DATABASE_NAME: str = "fleetpulse_db"
    FRONTEND_URL: str = "http://localhost:5173"
    JWT_SECRET_KEY: str

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()