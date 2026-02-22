import os
import logging
from typing import Any

logger = logging.getLogger("observability.sentry")


def init_sentry(app: Any = None) -> bool:
    """Guarded Sentry init.

    No-ops when `SENTRY_DSN` is not set or `sentry_sdk` is unavailable.
    If `app` is provided and the ASGI integration is available, attempts
    to attach the ASGI middleware.
    Returns True if Sentry was initialized, False otherwise.
    """
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return False
    try:
        import sentry_sdk

        sentry_kwargs = {}
        env = os.getenv("SENTRY_ENVIRONMENT")
        if env:
            sentry_kwargs["environment"] = env
        release = os.getenv("SENTRY_RELEASE")
        if release:
            sentry_kwargs["release"] = release
        traces = os.getenv("SENTRY_TRACES_SAMPLE_RATE")
        if traces:
            try:
                sentry_kwargs["traces_sample_rate"] = float(traces)
            except Exception:
                pass

        sentry_sdk.init(dsn=dsn, **sentry_kwargs)

        # Optionally attach ASGI middleware for performance tracing and
        # better context propagation if available.
        if app is not None:
            try:
                from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

                try:
                    # FastAPI/Starlette: prefer add_middleware when possible
                    app.add_middleware(SentryAsgiMiddleware)
                except Exception:
                    # Fallback: wrap the app (best-effort)
                    # This may replace the local reference but will still
                    # instrument the running application object in many
                    # deployment setups.
                    app = SentryAsgiMiddleware(app)  # type: ignore
            except Exception:
                # If the integration isn't available, continue silently.
                pass

        return True
    except Exception:
        logger.exception("sentry_init_failed")
        return False
