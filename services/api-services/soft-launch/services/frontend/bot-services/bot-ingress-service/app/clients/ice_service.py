from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from ..core.config import Settings


async def hydrate_session_ingress(
    client: httpx.AsyncClient,
    settings: Settings,
    *,
    event_id: str,
    session_id: str,
    from_number: str,
    to_number: str,
    platform: str,
) -> Optional[Dict[str, Any]]:
    """Hydrate session for ingress with minimal params.
    
    ICE will resolve:
    - Bot by to_number
    - User by from_number
    - Business context
    - Session state & expected action
    - Service tokens
    - Catalog context
    - Affiliate context (if applicable)
    
    Returns: HydrateSessionResponse dict or None on failure
    """
    if not settings.ice_service_url:
        return None

    url = f"{settings.ice_service_url.rstrip('/')}/api/v1/hydrate/session"
    
    payload: Dict[str, Any] = {
        "event_id": event_id,
        "session_id": session_id,
        "from_number": from_number,
        "to_number": to_number,
        "platform": platform,
    }

    try:
        resp = await client.post(url, json=payload, timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        return None
    except Exception:
        return None


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
    required_blobs: Optional[list[str]] = None,
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
        "required_blobs": required_blobs or ["session", "order_draft", "bot_meta"],
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


async def log_incoming_message(
    client: httpx.AsyncClient,
    settings: Settings,
    *,
    correlation_id: str,
    session_id: str,
    user_phone: str,
    bot_phone: str,
    incoming_message: Optional[str],
    incoming_payload: Dict[str, Any],
    incoming_at: Optional[str],
) -> bool:
    """Log incoming message in ICE (single-row in/out log)."""
    if not settings.ice_service_url:
        return False

    url = f"{settings.ice_service_url.rstrip('/')}/api/v1/messages/log"
    payload: Dict[str, Any] = {
        "correlation_id": correlation_id,
        "session_id": session_id,
        "user_phone": user_phone,
        "bot_phone": bot_phone,
        "incoming_message": incoming_message,
        "incoming_payload": incoming_payload,
        "incoming_at": incoming_at,
    }

    try:
        resp = await client.post(url, json=payload, timeout=10.0)
        resp.raise_for_status()
        return True
    except httpx.HTTPStatusError:
        return False
    except Exception:
        return False
