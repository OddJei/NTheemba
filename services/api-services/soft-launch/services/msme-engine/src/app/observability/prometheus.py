from __future__ import annotations

import os
import logging
from typing import Optional

logger = logging.getLogger("observability.prometheus")

def ensure_multiproc_dir() -> Optional[str]:
    """Ensure `PROMETHEUS_MULTIPROC_DIR` is set when running multiple Python processes.

    Returns the directory path if set or created, otherwise None.
    """
    d = os.getenv("PROMETHEUS_MULTIPROC_DIR")
    if d:
        return d

    # Do not attempt to create by default; leave to orchestration. Log a hint.
    logger.debug("PROMETHEUS_MULTIPROC_DIR not set; using single-process metrics")
    return None
