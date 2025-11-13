
"""Configuration settings with compatibility for pydantic v1 and v2.

This module tries to use pydantic-settings (pydantic v2). If it's not
available, it falls back to pydantic v1 compatible BaseSettings. If
neither is available, it uses a tiny plain-objects fallback that reads
environment variables directly.
"""
import os
from typing import Optional
from pathlib import Path

# Load .env into the process environment when present so a fallback
# settings implementation (or code that doesn't use pydantic-settings)
# can still read DATABASE_URL and other vars.
try:
    from dotenv import load_dotenv
    _dotenv_path = Path(__file__).resolve().parents[2] / ".env"
    if _dotenv_path.exists():
        load_dotenv(_dotenv_path)
except Exception:
    # python-dotenv is optional here; if it's not installed we'll just
    # rely on existing environment variables.
    pass


try:
    # pydantic v2: prefer pydantic-settings
    from pydantic_settings import BaseSettings  # type: ignore
    from pydantic import SettingsConfigDict  # type: ignore
    _PD2 = True
except Exception:
    try:
        # pydantic v1: BaseSettings lives in pydantic
        from pydantic import BaseSettings  # type: ignore
        _PD2 = False
    except Exception:
        BaseSettings = None  # type: ignore
        _PD2 = None


def _default_env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return v if v is not None else default


if BaseSettings is not None:

    class Settings(BaseSettings):
        DATABASE_URL: str = _default_env("DATABASE_URL", "sqlite:///./dev_notifications.db")
        REDIS_URL: str = _default_env("REDIS_URL", "redis://localhost:6379/0")
        SMS_GATEWAY_URL: str = _default_env("SMS_GATEWAY_URL", "") or ""
        EMAIL_GATEWAY_URL: str = _default_env("EMAIL_GATEWAY_URL", "") or ""
        SERVICE_PORT: int = int(_default_env("SERVICE_PORT", "8000") or 8000)
        NOTIFIER_GRPC_TARGET: str = _default_env("NOTIFIER_GRPC_TARGET", "") or ""
        # Where to POST audit events (external audit service)
        AUDIT_URL: str = _default_env("AUDIT_URL", "http://localhost:8290/audit/log") or "http://localhost:8290/audit/log"
        # Toggle whether audit events should be posted externally. Accepts 1/0 or true/false strings.
        AUDIT_ENABLED: bool = _default_env("AUDIT_ENABLED", "1") in ("1", "true", "True", "yes", "Yes")
        # Toggle whether outbound notifier calls should be made. When false the
        # service will not call external notifier gateways and will instead log
        # the notification locally for debugging.
        NOTIFIER_ENABLED: bool = _default_env("NOTIFIER_ENABLED", "1") in ("1", "true", "True", "yes", "Yes")

        @property
        def ASYNC_DATABASE_URL(self) -> str:
            # Convert DATABASE_URL to an async driver url for SQLAlchemy
            url = self.DATABASE_URL
            if url.startswith("sqlite") and "aiosqlite" not in url:
                return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
            if "psycopg2" in url:
                return url.replace("psycopg2", "asyncpg")
            if url.startswith("postgresql://") and "+asyncpg" not in url:
                return url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url

        if _PD2:
            model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
        else:
            class Config:  # type: ignore
                env_file = ".env"


    settings = Settings()

    # Ensure AUDIT_ENABLED exists on the settings instance regardless of
    # how pydantic interpreted the class defaults. This keeps runtime
    # toggling (via run.py) reliable.
    if not hasattr(settings, "AUDIT_ENABLED"):
        settings.AUDIT_ENABLED = _default_env("AUDIT_ENABLED", "1") in ("1", "true", "True", "yes", "Yes")
    if not hasattr(settings, "NOTIFIER_ENABLED"):
        settings.NOTIFIER_ENABLED = _default_env("NOTIFIER_ENABLED", "1") in ("1", "true", "True", "yes", "Yes")
else:

    class Settings:
        def __init__(self) -> None:
            self.DATABASE_URL = _default_env("DATABASE_URL", "sqlite:///./dev_notifications.db")
            self.REDIS_URL = _default_env("REDIS_URL", "redis://localhost:6379/0")
            self.SMS_GATEWAY_URL = _default_env("SMS_GATEWAY_URL", "") or ""
            self.EMAIL_GATEWAY_URL = _default_env("EMAIL_GATEWAY_URL", "") or ""
            self.SERVICE_PORT = int(_default_env("SERVICE_PORT", "8000") or 8000)
            self.NOTIFIER_GRPC_TARGET = _default_env("NOTIFIER_GRPC_TARGET", "") or ""
            self.AUDIT_URL = _default_env("AUDIT_URL", "http://localhost:8290/audit/log") or "http://localhost:8290/audit/log"

        @property
        def ASYNC_DATABASE_URL(self) -> str:
            url = self.DATABASE_URL
            if url.startswith("sqlite") and "aiosqlite" not in url:
                return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
            if "psycopg2" in url:
                return url.replace("psycopg2", "asyncpg")
            if url.startswith("postgresql://") and "+asyncpg" not in url:
                return url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url


    settings = Settings()

    # Fallback instance: ensure AUDIT_ENABLED is always present
    if not hasattr(settings, "AUDIT_ENABLED"):
        settings.AUDIT_ENABLED = _default_env("AUDIT_ENABLED", "1") in ("1", "true", "True", "yes", "Yes")
    if not hasattr(settings, "NOTIFIER_ENABLED"):
        settings.NOTIFIER_ENABLED = _default_env("NOTIFIER_ENABLED", "1") in ("1", "true", "True", "yes", "Yes")


