from __future__ import annotations

import os
from fastapi import FastAPI


def instrument_app(app: FastAPI) -> FastAPI:
    """Guarded Sentry instrumentation.

    - No-op when `SENTRY_DSN` is unset.
    - Initializes `sentry_sdk` with common env vars and wraps the ASGI app
      with the Sentry ASGI middleware for automatic error/trace capture.
    """
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return app

    try:
        import sentry_sdk
        from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

        sentry_sdk.init(
            dsn=dsn,
            environment=os.getenv("SENTRY_ENVIRONMENT", None),
            release=os.getenv("SENTRY_RELEASE", None),
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0")),
        )
        return SentryAsgiMiddleware(app)
    except Exception:
        # If sentry is not installed or init fails, leave the app unmodified.
        return app
