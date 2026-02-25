from __future__ import annotations

import os


def get_database_url() -> str:
    # Prefer explicit `DATABASE_URL`. Otherwise build from Postgres env vars.
    explicit = os.getenv("DATABASE_URL")
    if explicit:
        return explicit

    pg_user = os.getenv("PG_USER")
    if not pg_user:
        return os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./msme_engine.db")

    pg_password = os.getenv("PG_PASSWORD", "")
    pg_host = os.getenv("PG_HOST", "127.0.0.1")
    pg_port = os.getenv("PG_PORT", "5432")
    pg_db = os.getenv("PG_DB", "ntheemba")
    # Build asyncpg SQLAlchemy URL; per-service schema applied at connection time.
    import urllib.parse

    quoted_pw = urllib.parse.quote_plus(pg_password)
    return f"postgresql+asyncpg://{pg_user}:{quoted_pw}@{pg_host}:{pg_port}/{pg_db}"


def get_pg_schema() -> str:
    return os.getenv("PG_SCHEMA", "msme_engine")


def get_jwt_secret() -> str:
    # In production require an explicit secret; do not fall back to a guessable default.
    val = os.getenv("MSME_JWT_SECRET")
    if os.getenv("ENV", "development") == "production":
        if not val:
            raise RuntimeError("MSME_JWT_SECRET must be set in production")
    return val or "change-me"


def get_required_secret(env_name: str, hint: str | None = None) -> str:
    """Fetch a required secret, with a hint for migrating to a secret manager.

    Raises RuntimeError in production if missing.
    """
    val = os.getenv(env_name)
    if os.getenv("ENV", "development") == "production" and not val:
        msg = f"{env_name} must be set in production"
        if hint:
            msg += f"; hint: {hint}"
        raise RuntimeError(msg)
    return val or ""


def get_access_token_minutes() -> int:
    return int(os.getenv("MSME_ACCESS_TOKEN_MINUTES", "60"))


def get_refresh_token_days() -> int:
    return int(os.getenv("MSME_REFRESH_TOKEN_DAYS", "30"))


def get_password_hash_iterations() -> int:
    return int(os.getenv("MSME_PBKDF2_ITERS", "210000"))


def get_notification_base_url() -> str:
    return os.getenv("NOTIFICATION_BASE_URL", "http://127.0.0.1:8570")


def get_notification_timeout_seconds() -> float:
    try:
        return float(os.getenv("NOTIFICATION_TIMEOUT_SECONDS", "3.0"))
    except ValueError:
        return 3.0


def get_payment_revenue_base_url() -> str:
    return os.getenv("PAYMENT_REVENUE_BASE_URL", "http://payment-revenue:8590")


def get_subscription_price_minor(plan: str) -> int:
    """Return default price in minor units for a plan. Configurable via env var `SUBSCRIPTION_PRICES` as CSV: paid:5000,free:0"""
    env = os.getenv("SUBSCRIPTION_PRICES")
    defaults = {"paid": 5000, "free": 0}
    if not env:
        return defaults.get(plan, 0)

    # parse CSV
    try:
        mapping = {}
        for part in env.split(","):
            k, v = part.split(":")
            mapping[k.strip()] = int(v.strip())
        return mapping.get(plan, defaults.get(plan, 0))
    except Exception:
        return defaults.get(plan, 0)


def get_subscription_currency(plan: str) -> str:
    return os.getenv("SUBSCRIPTION_CURRENCY", "ZMW")
