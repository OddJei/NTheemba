from __future__ import annotations

import os
import logging
from typing import Optional


def init_sentry_from_env() -> None:
    """Initialize Sentry SDK if `SENTRY_DSN` is set.

    This function is guarded: if `sentry-sdk` isn't installed or `SENTRY_DSN`
    is not present, it no-ops.
    """
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration
    except Exception:
        # sentry-sdk missing in the environment; don't raise at runtime.
        logging.getLogger("affiliate_engine").warning(
            "sentry-sdk not installed; skipping Sentry initialization"
        )
        return

    environment = os.getenv("ENVIRONMENT") or os.getenv("APP_ENV") or os.getenv("PYTHON_ENV") or "production"
    release = os.getenv("SENTRY_RELEASE")
    traces_sample_rate = 0.0
    try:
        traces_sample_rate = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0"))
    except Exception:
        traces_sample_rate = 0.0

    logging_integration = LoggingIntegration(level=None, event_level=None)

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        traces_sample_rate=traces_sample_rate,
        integrations=[logging_integration],
    )


def instrument_app(app) -> object:
    """Wrap the ASGI `app` with Sentry ASGI middleware if `SENTRY_DSN` is set

    Returns the original or wrapped app. This is guarded: if `sentry-sdk` or
    the ASGI integration isn't available, it returns the original app.
    """
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return app

    try:
        from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
    except Exception:
        logging.getLogger("affiliate_engine").warning(
            "sentry-sdk ASGI integration not available; skipping middleware"
        )
        return app

    try:
        wrapped = SentryAsgiMiddleware(app)
        return wrapped
    except Exception:
        logging.getLogger("affiliate_engine").exception("sentry_wrap_failed")
        return app
