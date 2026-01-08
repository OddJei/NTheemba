from __future__ import annotations

import os


def get_database_url() -> str:
    # Matches other soft-launch services (SQLite by default)
    return os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./order_delivery.db")
