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
    return os.getenv("MSME_BASE_URL", "http://127.0.0.1:8501")


def require_product_links() -> bool:
    return os.getenv("AFFILIATE_REQUIRE_PRODUCT_LINKS", "0") in ("1", "true", "True")
