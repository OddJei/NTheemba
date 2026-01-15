from __future__ import annotations

import os


def get_database_url() -> str:
    # Matches other soft-launch services (SQLite by default)
    return os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./order_delivery.db")


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
