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
