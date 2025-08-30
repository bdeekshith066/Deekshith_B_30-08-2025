# App configuration using Pydantic BaseSettings (loads from .env or defaults).

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./store_monitor.sqlite"

    STATUS_CSV: str | None = None
    HOURS_CSV: str | None = None
    TZ_CSV: str | None = None

    class Config:
        env_file = ".env"

settings = Settings()
