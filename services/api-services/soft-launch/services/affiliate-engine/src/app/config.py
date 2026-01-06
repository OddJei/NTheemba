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
