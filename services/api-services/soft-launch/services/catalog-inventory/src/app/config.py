from __future__ import annotations

import os


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./catalog_inventory.db")


def get_event_source() -> str:
    return os.getenv("EVENT_SOURCE", "catalog-inventory")
