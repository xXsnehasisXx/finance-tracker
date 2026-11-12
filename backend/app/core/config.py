"""Environment-driven settings. Secrets come only from the environment / .env (never hardcoded)."""
import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_env: str
    poc_id: str
    associate_id: str
    phase: int
    database_url: str
    secret_key: str
    access_token_expire_minutes: int
    cors_origins: list
    otel_console: bool


@lru_cache
def get_settings() -> Settings:
    secret = os.getenv("SECRET_KEY", "")
    if not secret:
        raise RuntimeError("SECRET_KEY is not set. Generate one: python -c \"import secrets; print(secrets.token_urlsafe(48))\"")
    app_env = os.getenv("APP_ENV", "development")
    return Settings(
        app_env=app_env,
        poc_id=os.getenv("POC_ID", "POC-02"),
        associate_id=os.getenv("ASSOCIATE_ID", "unknown"),
        phase=int(os.getenv("PHASE", "1")),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./finance_tracker.db"),
        secret_key=secret,
        access_token_expire_minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")),
        cors_origins=[o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()],
        otel_console=os.getenv("OTEL_CONSOLE", "true" if app_env != "test" else "false").lower() == "true",
    )
