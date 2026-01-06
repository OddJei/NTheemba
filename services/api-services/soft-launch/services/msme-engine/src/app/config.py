from __future__ import annotations

import os


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./msme_engine.db")


def get_jwt_secret() -> str:
    return os.getenv("MSME_JWT_SECRET", "change-me")


def get_access_token_minutes() -> int:
    return int(os.getenv("MSME_ACCESS_TOKEN_MINUTES", "60"))


def get_refresh_token_days() -> int:
    return int(os.getenv("MSME_REFRESH_TOKEN_DAYS", "30"))


def get_password_hash_iterations() -> int:
    return int(os.getenv("MSME_PBKDF2_ITERS", "210000"))
