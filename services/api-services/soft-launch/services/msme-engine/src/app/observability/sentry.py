from __future__ import annotations

import os
import logging
from typing import Optional

logger = logging.getLogger("observability.sentry")

def init_sentry() -> Optional[bool]:
    """Initialize Sentry if SENTRY_DSN is provided via env vars.

    Returns True when initialized, False when DSN unset, or None on error.
    """
    try:
        dsn = os.getenv("SENTRY_DSN")
        if not dsn:
            logger.debug("Sentry DSN not set; skipping Sentry init")
            return False

        # Lazy import so tests/dev without sentry sdk don't fail unless DSN present
        try:
            import sentry_sdk
        except Exception:
            logger.exception("sentry-sdk not installed; cannot initialize Sentry")
            return None

        env = os.getenv("SENTRY_ENVIRONMENT") or os.getenv("ENVIRONMENT")
        release = os.getenv("SENTRY_RELEASE")
        traces = os.getenv("SENTRY_TRACES_SAMPLE_RATE")
        traces_rate = None
        if traces:
            try:
                traces_rate = float(traces)
            except Exception:
                traces_rate = None

        sentry_sdk.init(
            dsn=dsn,
            environment=env,
            release=release,
            traces_sample_rate=traces_rate if traces_rate is not None else 0.0,
        )
        logger.info("Sentry initialized", extra={"environment": env, "release": release})
        return True
    except Exception:
        logger.exception("failed_initializing_sentry")
        return None
