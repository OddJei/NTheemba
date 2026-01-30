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


def get_msme_base_url() -> str:
    """Return the MSME engine base URL for validating businesses.

    Default matches the local port used by the msme-engine in the soft-launch.
    """
    return os.getenv("MSME_BASE_URL", "http://127.0.0.1:8500")


def get_notification_base_url() -> str:
    return os.getenv("NOTIFICATION_BASE_URL", "http://127.0.0.1:8570")


def get_notification_timeout_seconds() -> float:
    try:
        return float(os.getenv("NOTIFICATION_TIMEOUT_SECONDS", "3.0"))
    except ValueError:
        return 3.0


def skip_msme_validation() -> bool:
    # Test/dev escape hatch: when enabled, product creation will not call MSME engine.
    return os.getenv("CATALOG_SKIP_MSME_VALIDATION", "0") in ("1", "true", "True")


def get_jwt_secret() -> str:
    # Shared secret used by msme-engine for issuing access tokens; other services verify with it.
    return os.getenv("MSME_JWT_SECRET", "change-me")
