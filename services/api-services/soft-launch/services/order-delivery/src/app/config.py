from __future__ import annotations

import os


def get_database_url() -> str:
    # Matches other soft-launch services (SQLite by default)
    return os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./order_delivery.db")


def get_pg_schema() -> str:
    # Optional schema name. If set and using Postgres, the service will ensure it exists.
    return os.getenv("PG_SCHEMA", "").strip()


def get_msme_base_url() -> str:
    # MSME Engine (Soft Launch)
    return os.getenv("MSME_BASE_URL", "http://127.0.0.1:8500")


def get_msme_timeout_seconds() -> float:
    try:
        return float(os.getenv("MSME_TIMEOUT_SECONDS", "3.0"))
    except ValueError:
        return 3.0


def get_notification_base_url() -> str:
    return os.getenv("NOTIFICATION_BASE_URL", "http://127.0.0.1:8570")


def get_notification_timeout_seconds() -> float:
    try:
        return float(os.getenv("NOTIFICATION_TIMEOUT_SECONDS", "3.0"))
    except ValueError:
        return 3.0


def get_affiliate_engine_base_url() -> str:
    return os.getenv("AFFILIATE_ENGINE_BASE_URL", "http://127.0.0.1:8510")


def get_affiliate_engine_timeout_seconds() -> float:
    try:
        return float(os.getenv("AFFILIATE_ENGINE_TIMEOUT_SECONDS", "3.0"))
    except ValueError:
        return 3.0


def get_bot_session_base_url() -> str:
    return os.getenv("BOT_SESSION_BASE_URL", "http://127.0.0.1:8610")


def get_bot_session_timeout_seconds() -> float:
    try:
        return float(os.getenv("BOT_SESSION_TIMEOUT_SECONDS", "2.0"))
    except ValueError:
        return 2.0


def get_jwt_secret() -> str:
    # Shared secret used by msme-engine for issuing access tokens; other services verify with it.
    return os.getenv("MSME_JWT_SECRET", "change-me")


def get_internal_service_secret() -> str:
    # Shared secret for internal service-to-service calls.
    # If set, callers may include header: X-Internal-Secret: <secret>
    return os.getenv("INTERNAL_SERVICE_SECRET", "")
