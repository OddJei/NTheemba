from __future__ import annotations

import os


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./catalog_inventory.db")


def get_event_source() -> str:
    return os.getenv("EVENT_SOURCE", "catalog-inventory")


def get_s3_settings() -> dict:
    """Return S3/MinIO settings from env with sensible defaults for local soft-launch.

    Expected env vars:
    - S3_ENDPOINT_URL
    - S3_ACCESS_KEY
    - S3_SECRET_KEY
    - S3_BUCKET
    - S3_REGION
    - S3_USE_SSL (1/0)
    """
    return {
        "endpoint_url": os.getenv("S3_ENDPOINT_URL", "http://127.0.0.1:9000"),
        "access_key": os.getenv("S3_ACCESS_KEY", "minioadmin"),
        "secret_key": os.getenv("S3_SECRET_KEY", "minioadmin"),
        "bucket": os.getenv("S3_BUCKET", "ntheemba"),
        "region": os.getenv("S3_REGION", "us-east-1"),
        "use_ssl": os.getenv("S3_USE_SSL", "0") in ("1", "true", "True"),
    }
