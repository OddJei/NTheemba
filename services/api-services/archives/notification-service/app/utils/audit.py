import asyncio
import json
import os
import logging
from typing import Any, Dict

import httpx
from app.config.settings import settings

logger = logging.getLogger("notification.audit")


async def log_event(service: str, event_type: str, actor_id: str, entity_type: str, entity_id: str, payload: Dict[str, Any], metadata: Dict[str, Any] = None) -> None:
    """Send an audit event to the configured audit service asynchronously.

    This helper will attempt to POST the event and ignore transient errors
    (best-effort). It's non-blocking for the caller.
    """
    data = {
        "service": service,
        "event_type": event_type,
        "actor_id": actor_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "payload": payload or {},
        "metadata": metadata or {},
    }

    # Respect runtime toggle to disable external audit posting. Prefer process
    # env override so tests can flip the behavior at runtime.
    env_val = os.getenv("AUDIT_ENABLED")
    audit_enabled = None
    if env_val is not None:
        audit_enabled = env_val.lower() in ("1", "true", "yes")
    else:
        audit_enabled = getattr(settings, "AUDIT_ENABLED", True)

    # When disabled we log a concise single-line JSON summary so it's easy to
    # capture with log aggregation and tests (caplog).
    if not audit_enabled:
        try:
            payload_summary = {"service": service, "event_type": event_type, "actor_id": actor_id, "entity_type": entity_type, "entity_id": entity_id}
            logger.info("AUDIT_DISABLED: %s", json.dumps(payload_summary))
        except Exception:
            logger.info("AUDIT_DISABLED: (could not serialize event)")
        return

    url = settings.AUDIT_URL

    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.post(url, json=data)
            resp.raise_for_status()
        except Exception:
            # Swallow errors from audit logging — auditing should not block
            # primary application flows. In a real system we'd retry or
            # push to a local DLQ/queue for later delivery.
            return
