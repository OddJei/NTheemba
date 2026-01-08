import os
import httpx
import logging

MSME_ENGINE_URL = os.getenv("MSME_ENGINE_URL", "http://127.0.0.1:8500")
logger = logging.getLogger("bot_session.events")


async def publish_business_event(business_id: str, event: dict) -> bool:
    """Publish event to msme-engine events endpoint (best-effort, async)."""
    if not business_id:
        return False
    try:
        url = f"{MSME_ENGINE_URL}/events/business/{business_id}"
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.post(url, json=event)
            if r.status_code in (200, 201, 202):
                return True
            logger.warning("publish_business_event failed %s %s", r.status_code, r.text)
    except Exception:
        logger.exception("publish_business_event exception")
    return False
