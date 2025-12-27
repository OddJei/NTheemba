from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from ..core.config import Settings


async def preload_session_context(
    client: httpx.AsyncClient,
    settings: Settings,
    *,
    event_id: str,
    session_id: str,
    user_phone: str,
    bot_id: str,
    platform: str,
    bot_type: str,
    business_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Ask ICE to preload/cache session context for this session.

    This is optional integration: if ICE_SERVICE_URL is empty, this returns None.
    The endpoint shape is intentionally generic; ICE can ignore unknown fields.
    """

    if not settings.ice_service_url:
        return None

    url = f"{settings.ice_service_url.rstrip('/')}{settings.ice_preload_path}"
    # Keep payload compatible with the bot-facing ICE hydrate contract.
    payload: Dict[str, Any] = {
        "event_id": event_id,
        "session_id": session_id,
        "user_phone": user_phone,
        "bot_id": bot_id,
        "platform": platform,
        "bot_type": bot_type,
        "reason": "ingress_cache_miss",
        "required_blobs": ["session", "order_draft", "bot_meta"],
    }
    if business_id:
        payload["business_id"] = business_id

    try:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, dict) else {"data": data}
    except httpx.HTTPStatusError:
        return None
    except Exception:
        return None
