from __future__ import annotations

import os


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./cart.db")


def get_event_source() -> str:
    return os.getenv("EVENT_SOURCE", "cart-service")


def get_catalog_base_url() -> str:
    return os.getenv("CATALOG_SERVICE_URL", "http://127.0.0.1:8520")


def get_notification_base_url() -> str:
    return os.getenv("NOTIFICATION_BASE_URL", "http://127.0.0.1:8570")


def get_notification_timeout_seconds() -> float:
    try:
        return float(os.getenv("NOTIFICATION_TIMEOUT_SECONDS", "3.0"))
    except ValueError:
        return 3.0
