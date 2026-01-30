from __future__ import annotations

import os


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./payment_revenue.db")


def get_msme_base_url() -> str:
    return os.getenv("MSME_BASE_URL", "http://127.0.0.1:8500")


def get_order_delivery_base_url() -> str:
    return os.getenv("ORDER_DELIVERY_BASE_URL", "http://127.0.0.1:8560")


def get_affiliate_engine_base_url() -> str:
    return os.getenv("AFFILIATE_ENGINE_BASE_URL", "http://127.0.0.1:8510")


def get_http_timeout_seconds() -> float:
    try:
        return float(os.getenv("HTTP_TIMEOUT_SECONDS", "4.0"))
    except ValueError:
        return 4.0


def get_affiliate_commission_share_of_platform_fee() -> float:
    # 0.0 -> no direct commission (pool can still be used)
    # 1.0 -> all platform fee goes to affiliate commission
    try:
        v = float(os.getenv("AFFILIATE_COMMISSION_SHARE", "0.0"))
    except ValueError:
        v = 0.0
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def get_minor_unit_scale() -> int:
    # Soft-launch default: 2 decimal places.
    # If you later support JPY-like currencies, make this currency-aware.
    try:
        v = int(os.getenv("MINOR_UNIT_SCALE", "2"))
    except ValueError:
        v = 2
    return 2 if v not in (0, 2, 3) else v


def get_notification_base_url() -> str:
    return os.getenv("NOTIFICATION_BASE_URL", "http://127.0.0.1:8570")


def get_notification_timeout_seconds() -> float:
    try:
        return float(os.getenv("NOTIFICATION_TIMEOUT_SECONDS", "3.0"))
    except ValueError:
        return 3.0


def get_payment_revenue_base_url() -> str:
    # Used for self-calls from the outbox flusher (runs inside this service container).
    # Prefer the compose service hostname so other containers can reach this service.
    return os.getenv("PAYMENT_REVENUE_BASE_URL", "http://payment-revenue:8590")


def get_internal_service_secret() -> str:
    # Shared secret for internal service-to-service calls.
    # If set, callers must include header: X-Internal-Secret: <secret>
    return os.getenv("INTERNAL_SERVICE_SECRET", "")


def get_outbox_flush_internal_secret() -> str:
    # Optional header added by the outbox flusher for internal-only endpoints.
    return os.getenv("OUTBOX_FLUSH_INTERNAL_SECRET") or get_internal_service_secret()


def get_jwt_secret() -> str:
    # Shared secret used by msme-engine for issuing access tokens; other services verify with it.
    return os.getenv("MSME_JWT_SECRET", "change-me")


def get_pawapay_base_url() -> str:
    # Include /v2 in the base URL.
    return os.getenv("PAWAPAY_BASE_URL", "https://api.sandbox.pawapay.io/v2")


def get_pawapay_api_key() -> str:
    # Keep compatibility with existing env naming.
    return os.getenv("PAWAPAY_API_KEY") or os.getenv("API_KEY", "")


def get_pawapay_webhook_secret() -> str:
    # Optional shared secret to protect callback endpoints.
    # If set, callbacks must include header: X-PawaPay-Secret: <secret>
    return os.getenv("PAWAPAY_WEBHOOK_SECRET", "")


def get_pawapay_reconcile_enabled() -> bool:
    return os.getenv("PAWAPAY_RECONCILE_ENABLED", "false").strip().lower() in {"1", "true", "yes", "y"}


def get_pawapay_reconcile_interval_seconds() -> int:
    # How often the background scheduler runs.
    try:
        v = int(os.getenv("PAWAPAY_RECONCILE_INTERVAL_SECONDS", "180"))
    except ValueError:
        v = 180
    return 30 if v < 30 else v


def get_pawapay_reconcile_stale_seconds() -> int:
    # Only reconcile rows not updated recently.
    try:
        v = int(os.getenv("PAWAPAY_RECONCILE_STALE_SECONDS", "900"))
    except ValueError:
        v = 900
    return 60 if v < 60 else v


def get_pawapay_reconcile_batch_size() -> int:
    try:
        v = int(os.getenv("PAWAPAY_RECONCILE_BATCH_SIZE", "50"))
    except ValueError:
        v = 50
    return 1 if v < 1 else (200 if v > 200 else v)


def get_outbox_flush_enabled() -> bool:
    return os.getenv("OUTBOX_FLUSH_ENABLED", "false").strip().lower() in {"1", "true", "yes", "y"}


def get_outbox_flush_interval_seconds() -> int:
    try:
        v = int(os.getenv("OUTBOX_FLUSH_INTERVAL_SECONDS", "30"))
    except ValueError:
        v = 30
    return 5 if v < 5 else v


def get_outbox_flush_batch_size() -> int:
    try:
        v = int(os.getenv("OUTBOX_FLUSH_BATCH_SIZE", "50"))
    except ValueError:
        v = 50
    return 1 if v < 1 else (200 if v > 200 else v)


def get_outbox_flush_max_attempts() -> int:
    try:
        # 0 means "never give up" (keep retrying with backoff).
        v = int(os.getenv("OUTBOX_FLUSH_MAX_ATTEMPTS", "0"))
    except ValueError:
        v = 0
    return 0 if v < 0 else (1000 if v > 1000 else v)


def get_outbox_flush_backoff_base_seconds() -> int:
    try:
        v = int(os.getenv("OUTBOX_FLUSH_BACKOFF_BASE_SECONDS", "10"))
    except ValueError:
        v = 10
    return 1 if v < 1 else (3600 if v > 3600 else v)


def get_msme_service_identifier() -> str:
    return os.getenv("MSME_SERVICE_IDENTIFIER", "service-account")


def get_msme_service_password() -> str:
    return os.getenv("MSME_SERVICE_PASSWORD", "change-me")


def get_outbox_flush_backoff_max_seconds() -> int:
    try:
        v = int(os.getenv("OUTBOX_FLUSH_BACKOFF_MAX_SECONDS", "300"))
    except ValueError:
        v = 300
    return 5 if v < 5 else (86400 if v > 86400 else v)


def get_pg_schema() -> str:
    # Optional schema name. If set and using Postgres, the service will ensure it exists.
    return os.getenv("PG_SCHEMA", "").strip()
