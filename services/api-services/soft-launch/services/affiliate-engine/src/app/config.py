from __future__ import annotations

import os
import urllib.parse


def get_database_url() -> str:
    """Return async DB URL.

    Prefer explicit `DATABASE_URL`. Otherwise build from Postgres env vars:
    - PG_USER, PG_PASSWORD, PG_HOST, PG_PORT, PG_DB

    For per-service schema, set `PG_SCHEMA` and the connection will include
    search_path via the `options` parameter when building the URL.
    Falls back to sqlite file for local quick dev if no PG_USER provided.
    """
    explicit = os.getenv("DATABASE_URL")
    if explicit:
        return explicit

    pg_user = os.getenv("PG_USER")
    if not pg_user:
        return os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./affiliate_engine.db")

    pg_password = os.getenv("PG_PASSWORD", "")
    pg_host = os.getenv("PG_HOST", "127.0.0.1")
    pg_port = os.getenv("PG_PORT", "5432")
    pg_db = os.getenv("PG_DB", "ntheemba")
    pg_schema = os.getenv("PG_SCHEMA", "affiliate_engine")

    # url-encode password
    quoted_pw = urllib.parse.quote_plus(pg_password)

    # Asyncpg + SQLAlchemy connection URL (do not pass `options` here because
    # asyncpg.connect() does not accept that kwarg). The per-service schema is
    # applied via `connect_args` when building the engine.
    return f"postgresql+asyncpg://{pg_user}:{quoted_pw}@{pg_host}:{pg_port}/{pg_db}"


def get_pg_schema() -> str:
    return os.getenv("PG_SCHEMA", "affiliate_engine")


def get_admin_key() -> str:
    return os.getenv("AFFILIATE_ADMIN_KEY", "change-me")


def get_epoch_days_default() -> int:
    return int(os.getenv("AFFILIATE_EPOCH_DAYS", "182"))


def get_pool_pct_default() -> float:
    return float(os.getenv("AFFILIATE_POOL_PCT", "0.10"))


def get_catalog_base_url() -> str:
    return os.getenv("CATALOG_BASE_URL", "http://127.0.0.1:8520")


def get_msme_base_url() -> str:
    return os.getenv("MSME_BASE_URL", "http://127.0.0.1:8500")


def require_product_links() -> bool:
    return os.getenv("AFFILIATE_REQUIRE_PRODUCT_LINKS", "0") in ("1", "true", "True")


def skip_link_target_validation() -> bool:
    # Test/dev escape hatch: when enabled, `POST /affiliates/{id}/links` will not call MSME/Catalog.
    return os.getenv("AFFILIATE_SKIP_LINK_TARGET_VALIDATION", "0") in ("1", "true", "True")


def get_notification_base_url() -> str:
    return os.getenv("NOTIFICATION_BASE_URL", "http://127.0.0.1:8570")


def get_payment_revenue_base_url() -> str:
    return os.getenv("PAYMENT_REVENUE_BASE_URL", "http://127.0.0.1:8560")


def get_notification_timeout_seconds() -> float:
    try:
        return float(os.getenv("NOTIFICATION_TIMEOUT_SECONDS", "3.0"))
    except ValueError:
        return 3.0


def get_jwt_secret() -> str:
    # Shared secret used by msme-engine for issuing access tokens; other services verify with it.
    return os.getenv("MSME_JWT_SECRET", "change-me")


def get_affiliate_token_ttl_seconds() -> int:
    """Short-lived WhatsApp token TTL (seconds)."""
    try:
        return int(os.getenv("AFFILIATE_TOKEN_TTL_SECONDS", "600"))
    except ValueError:
        return 600


def get_affiliate_token_prefix() -> str:
    # Prefix included in the WhatsApp message body so the bot can detect tokens.
    return os.getenv("AFFILIATE_TOKEN_PREFIX", "ace:")


def get_affiliate_default_whatsapp_number() -> str | None:
    """Fallback WhatsApp number if MSME service doesn't provide one.

    Format: digits with country code, e.g. 26097xxxxxxx. (Leading + allowed; it will be stripped.)
    """
    v = os.getenv("AFFILIATE_DEFAULT_WHATSAPP_NUMBER", "").strip()
    return v or None
