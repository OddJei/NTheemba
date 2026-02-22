import os
import logging
from typing import Optional, Any

logger = logging.getLogger("observability.prometheus")


def create_registry() -> Optional[Any]:
    try:
        from prometheus_client import CollectorRegistry

        registry = CollectorRegistry()
        mp_dir = os.getenv("PROMETHEUS_MULTIPROC_DIR")
        if mp_dir:
            try:
                # Multi-process collector requires the multiprocess module
                from prometheus_client import multiprocess

                multiprocess.MultiProcessCollector(registry)
            except Exception:
                # If multiprocess support fails, fall back to a simple registry
                pass
        return registry
    except Exception:
        return None


def mount_metrics(app: Any, path: str = "/metrics") -> bool:
    """Mount a Prometheus ASGI `/metrics` endpoint on the given app.

    Returns True if the metrics endpoint was mounted, False otherwise.
    """
    try:
        from prometheus_client import make_asgi_app

        registry = create_registry()
        if registry is None:
            return False
        app.mount(path, make_asgi_app(registry=registry))
        return True
    except Exception:
        logger.exception("mount_metrics_failed")
        return False
