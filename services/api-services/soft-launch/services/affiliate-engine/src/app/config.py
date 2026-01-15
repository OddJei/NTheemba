from __future__ import annotations

import os


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./affiliate_engine.db")


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


def get_notification_timeout_seconds() -> float:
    try:
        return float(os.getenv("NOTIFICATION_TIMEOUT_SECONDS", "3.0"))
    except ValueError:
        return 3.0
