"""Lightweight observability helpers for bot-session.

Provides a small, guarded integration for Sentry and Prometheus so the
service can be instrumented when the necessary environment variables and
packages are present. Calling `instrument_app(app)` is safe in any
environment (it will no-op when libs or env vars are missing).
"""
from typing import Any


def instrument_app(app: Any) -> None:
    """Initialize observability for the given ASGI app.

    - Initializes Sentry if `SENTRY_DSN` is set and `sentry-sdk` is available.
    - Mounts a Prometheus `/metrics` ASGI app if `prometheus_client` is
      available (and `PROMETHEUS_MULTIPROC_DIR` is respected).
    """
    # Import lazily to avoid hard dependency at import time.
    try:
        from . import sentry as _sentry
    except Exception:
        _sentry = None  # type: ignore

    try:
        from . import prometheus as _prom
    except Exception:
        _prom = None  # type: ignore

    if _sentry is not None:
        try:
            _sentry.init_sentry(app)
        except Exception:
            # Keep observability best-effort: failures should not stop app.
            pass

    if _prom is not None:
        try:
            _prom.mount_metrics(app)
        except Exception:
            pass
