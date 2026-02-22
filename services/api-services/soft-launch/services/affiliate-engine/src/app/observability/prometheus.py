from __future__ import annotations

import os
from prometheus_client import CollectorRegistry, multiprocess


def get_registry() -> CollectorRegistry:
    """Return a CollectorRegistry suitable for the runtime.

    If `PROMETHEUS_MULTIPROC_DIR` is set we register a multi-process collector
    so metrics from multiple worker processes (gunicorn/uvicorn) are available.
    Otherwise return a fresh single-process registry.
    """
    mp_dir = os.getenv("PROMETHEUS_MULTIPROC_DIR")
    if mp_dir:
        reg = CollectorRegistry()
        multiprocess.MultiProcessCollector(reg)
        return reg
    return CollectorRegistry()
