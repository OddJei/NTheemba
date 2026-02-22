"""Service helper wrappers for MSME lookups and delivery (Outbox vs direct-post).

Use these helpers from orchestration workflows to centralize adapter calls
and the Outbox vs direct-post decision.
"""
from __future__ import annotations
from typing import Any, Dict, Optional
import os
import logging
import json

import aiohttp

from app.adapters.factory import AdapterFactory
from libs.outbox.outbox import create_outbox_row

logger = logging.getLogger(__name__)


async def get_service_token(business_id: str) -> Optional[str]:
    """Fetch a service JWT for `business_id` from MSME.

    Returns the access token string or None on failure.
    """
    try:
        msme = AdapterFactory.get_msme_adapter()
        session = await msme._get_session()
        headers = msme._build_headers()
        async with session.post(f"{msme.base_url}/auth/service-token/{business_id}", headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("access_token")
            logger.warning("get_service_token: non-200 status %s", resp.status)
            return None
    except Exception as e:
        logger.exception("get_service_token failed: %s", e)
        return None


async def get_user_by_phone(phone: str) -> Dict[str, Any]:
    """Lookup user by phone via MSME adapter."""
    try:
        msme = AdapterFactory.get_msme_adapter()
        return await msme.get_user_by_phone(phone)
    except Exception as e:
        logger.exception("get_user_by_phone failed: %s", e)
        return {}


async def get_business_by_phone(phone: str) -> Dict[str, Any]:
    """Lookup business by phone via MSME adapter."""
    try:
        msme = AdapterFactory.get_msme_adapter()
        return await msme.get_business_by_phone(phone)
    except Exception as e:
        logger.exception("get_business_by_phone failed: %s", e)
        return {}


async def get_business_by_id(business_id: str) -> Dict[str, Any]:
    """Fetch business profile + policies from MSME and merge into a single dict."""
    try:
        msme = AdapterFactory.get_msme_adapter()
        profile = await msme.fetch_business_profile(business_id)
        policies = await msme.fetch_business_policies(business_id)
        return {"profile": profile or {}, "policies": policies or {}}
    except Exception as e:
        logger.exception("get_business_by_id failed: %s", e)
        return {}


async def deliver(
    payload: Dict[str, Any],
    target: str,
    *,
    reliable: bool = True,
    db_session: Optional[Any] = None,
    correlation_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Deliver `payload` to `target` either reliably (Outbox) or as a fast direct POST.

    - If `reliable` is True the caller MUST pass a `db_session` (SQLAlchemy session).
      This will call `create_outbox_row(db_session, ...)` and return a small result.
    - If `reliable` is False a direct HTTP post is attempted and the remote response is returned.

    Returns a dict with `status` and optional `response`/`error` fields.
    """
    if reliable:
        if db_session is None:
            raise ValueError("db_session required for reliable deliver (Outbox write)")
        # Derive an event_type if provided in payload, else use generic
        event_type = payload.get("event_type") or "outbox.event"
        try:
            await create_outbox_row(db_session, event_type, payload, correlation_id=correlation_id, idempotency_key=idempotency_key)
            return {"status": "queued"}
        except Exception as e:
            logger.exception("deliver (outbox) failed: %s", e)
            return {"status": "error", "error": str(e)}

    # Direct POST path for fast UX
    try:
        async with aiohttp.ClientSession() as session:
            headers = {"Content-Type": "application/json"}
            async with session.post(target, data=json.dumps(payload), headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                text = await resp.text()
                try:
                    data = await resp.json()
                except Exception:
                    data = {"text": text}
                return {"status": "posted", "code": resp.status, "response": data}
    except Exception as e:
        logger.exception("deliver (direct) failed: %s", e)
        return {"status": "error", "error": str(e)}


# ----- Bot / Session helpers (bot-session service) -----


async def create_bot(
    phone: str,
    *,
    bot_type: str = "ice",
    name: Optional[str] = None,
    business_id: Optional[str] = None,
    auth_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Create a bot in the bot-session service (POST /bot/create).

    Returns the created bot object or empty dict on failure.
    """
    try:
        adapter = AdapterFactory.get_bot_session_adapter()
        client = await adapter._get_client()
        payload = {"phone": phone, "bot_type": bot_type}
        if name:
            payload["name"] = name
        if business_id:
            payload["business_id"] = business_id

        if auth_headers is not None:
            resp = await client.post(f"{adapter.base_url}/bot/create", json=payload, headers=auth_headers)
        else:
            resp = await client.post(f"{adapter.base_url}/bot/create", json=payload)
        if resp.status_code in (200, 201):
            return resp.json()
        logger.error("create_bot failed %s %s", resp.status_code, resp.text)
        return {}
    except Exception as e:
        logger.exception("create_bot error: %s", e)
        return {}


async def get_bot_by_phone(phone: str, auth_headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Lookup a bot by phone (GET /bot/by-phone/{phone})."""
    try:
        adapter = AdapterFactory.get_bot_session_adapter()
        client = await adapter._get_client()
        if auth_headers is not None:
            resp = await client.get(f"{adapter.base_url}/bot/by-phone/{phone}", headers=auth_headers)
        else:
            resp = await client.get(f"{adapter.base_url}/bot/by-phone/{phone}")
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 404:
            return {}
        logger.error("get_bot_by_phone failed %s %s", resp.status_code, resp.text)
        return {}
    except Exception as e:
        logger.exception("get_bot_by_phone error: %s", e)
        return {}


async def create_user_bot_session(
    user_phone: str,
    business_id: str,
    metadata: Dict[str, Any],
    auth_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Create or reactivate a user-bot session via UserBotConversationAdapter.

    Returns the session object (including `session_id`) or raises on error.
    """
    adapter = AdapterFactory.get_user_bot_session_adapter()
    try:
        client = await adapter._get_client()

        # Build payload mirroring adapter.create_session
        payload = {
            "user_phone": user_phone,
            "platform": metadata.get("platform", "whatsapp"),
            "business_id": business_id,
        }
        for k in ("bot_id", "bot_phone", "bot_type", "affiliate_id", "affiliate_metadata"):
            if k in metadata:
                payload[k] = metadata[k]

        if auth_headers is not None:
            response = await client.post(f"{adapter.base_url}/session/create", json=payload, headers=auth_headers)
        else:
            response = await client.post(f"{adapter.base_url}/session/create", json=payload)
        if response.status_code in (200, 201):
            return response.json()

        logger.error(
            "Failed to create session for %s: %s %s",
            user_phone,
            response.status_code,
            response.text,
        )
        return {}
    except Exception as e:
        logger.exception("create_user_bot_session failed: %s", e)
        return {}


async def create_session_state(
    session_id: str,
    state: str,
    object_context: Optional[Dict[str, Any]] = None,
    auth_headers: Optional[Dict[str, str]] = None,
) -> bool:
    """Create or set session state for `session_id`.

    This will attempt to call POST /session/{session_id}/state. If the
    downstream endpoint does not exist it will log and return False.
    """
    adapter = AdapterFactory.get_user_bot_session_adapter()
    try:
        client = await adapter._get_client()
        payload = {"state": state}
        if object_context is not None:
            payload["object_context"] = object_context

        if auth_headers is not None:
            resp = await client.post(f"{adapter.base_url}/session/{session_id}/state", json=payload, headers=auth_headers)
        else:
            resp = await client.post(f"{adapter.base_url}/session/{session_id}/state", json=payload)
        if resp.status_code in (200, 201):
            return True
        logger.warning("create_session_state returned %s %s", resp.status_code, resp.text)
        return False
    except Exception as e:
        logger.exception("create_session_state error: %s", e)
        return False


async def persist_and_cache_blob(
    key: str,
    blob: Dict[str, Any],
    *,
    session_id: Optional[str] = None,
    ttl: int = 3600,
) -> Dict[str, Any]:
    """Persist `blob` and cache it for fast reads.

    - Tries to cache the blob in Redis (async) if `REDIS_URL` is configured.
    - If `session_id` is provided, attempts to persist a copy by calling
      `create_session_state(session_id, state=f"blob:{key}", object_context={...})`.

    Returns a dict with keys: `cached` (bool) and `persisted` (bool).
    """
    result = {"cached": False, "persisted": False}
    try:
        # Try async redis first
        try:
            import redis.asyncio as aioredis

            redis_url = os.getenv("REDIS_URL")
            if redis_url:
                client = aioredis.from_url(redis_url, decode_responses=True)
                await client.set(key, json.dumps(blob))
                await client.expire(key, ttl)
                result["cached"] = True
        except Exception:
            # best-effort: try sync redis as fallback
            try:
                import redis

                redis_url = os.getenv("REDIS_URL")
                if redis_url:
                    r = redis.from_url(redis_url, decode_responses=True)
                    r.set(key, json.dumps(blob))
                    r.expire(key, ttl)
                    result["cached"] = True
            except Exception:
                logger.debug("redis cache unavailable for key %s", key)

        # Persist in DB (repository) if configured
        try:
            from app.state.repository import AsyncSessionLocal, IceRepository

            async with AsyncSessionLocal() as db:
                repo = IceRepository(db)
                await repo.save_hydrated_blob(key, blob)
                result["persisted"] = True
        except Exception:
            # fallback: try create_session_state via bot-session
            if session_id:
                try:
                    ok = await create_session_state(session_id, state=f"blob:{key}", object_context={"blob": blob})
                    result["persisted"] = bool(ok)
                except Exception:
                    logger.exception("persist_and_cache_blob: create_session_state failed")

    except Exception:
        logger.exception("persist_and_cache_blob failed")

    return result


async def ensure_user_exists(phone: str, *, display_name: str | None = None) -> Dict[str, Any]:
    """Ensure a user exists for `phone`.

    - Try to fetch via MSME (`get_user_by_phone`).
    - If not found, attempt to create a minimal user via MSME POST /auth/register (best-effort).
    - If creation fails, return a generated placeholder user dict.
    """
    try:
        # First try lookup
        user = await get_user_by_phone(phone)
        if user:
            return user

        # Try to create via MSME adapter if available
        try:
            from app.adapters.factory import AdapterFactory

            msme = AdapterFactory.get_msme_adapter()
            session = await msme._get_session()
            headers = msme._build_headers()
            payload = {"phone": phone, "name": display_name or "unknown", "role": "customer"}
            async with session.post(f"{msme.base_url}/auth/register", json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status in (200, 201):
                    data = await resp.json()
                    return data
        except Exception:
            logger.debug("msme create user not available or failed")

        # Fallback: generate a small placeholder user record
        from uuid import uuid4
        return {"id": str(uuid4()), "phone": phone, "name": display_name or "unknown", "role": "customer", "created_placeholder": True}
    except Exception:
        logger.exception("ensure_user_exists failed")
        from uuid import uuid4
        return {"id": str(uuid4()), "phone": phone, "name": display_name or "unknown", "role": "customer", "created_placeholder": True}


async def upgrade_cycle_state(
    session_id: str,
    new_state: str,
    *,
    metadata: Optional[Dict[str, Any]] = None,
    auth_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Advance or create a SessionStateCycle for `session_id`.

    Attempts POST /session/{session_id}/cycles with payload {state, metadata}.
    Returns the created/updated cycle object or empty dict on failure.
    """
    adapter = AdapterFactory.get_user_bot_session_adapter()
    try:
        client = await adapter._get_client()
        payload = {"state": new_state, "metadata": metadata or {}}
        if auth_headers is not None:
            resp = await client.post(f"{adapter.base_url}/session/{session_id}/cycles", json=payload, headers=auth_headers)
        else:
            resp = await client.post(f"{adapter.base_url}/session/{session_id}/cycles", json=payload)
        if resp.status_code in (200, 201):
            return resp.json()
        logger.warning("upgrade_cycle_state failed %s %s", resp.status_code, resp.text)
        return {}
    except Exception as e:
        logger.exception("upgrade_cycle_state error: %s", e)
        return {}


async def close_user_bot_session(session_id: str, reason: str = "user_exit", auth_headers: Optional[Dict[str, str]] = None) -> bool:
    """Close a user-bot session using a direct POST so auth headers can be supplied."""
    adapter = AdapterFactory.get_user_bot_session_adapter()
    try:
        client = await adapter._get_client()
        if auth_headers is not None:
            resp = await client.post(f"{adapter.base_url}/session/{session_id}/close", headers=auth_headers)
        else:
            resp = await client.post(f"{adapter.base_url}/session/{session_id}/close")
        if resp.status_code == 404:
            logger.warning("Session %s not found for closure", session_id)
            return False
        if resp.status_code == 200:
            return True
        logger.error("Failed to close session %s: %s %s", session_id, resp.status_code, resp.text)
        return False
    except Exception as e:
        logger.exception("close_user_bot_session error: %s", e)
        return False


# ----- Cart helpers (use Cart service endpoints) -----


async def create_cart_draft(
    session_id: str,
    user_phone: str,
    business_id: Optional[str] = None,
    *,
    idempotency_key: Optional[str] = None,
    auth_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Create a cart draft via Cart service (POST /cart/create)."""
    try:
        adapter = AdapterFactory.get_cart_order_adapter()
        # Use adapter method which handles auth headers and session creation
        payload: Dict[str, Any] = {"session_id": session_id, "user_phone": user_phone}
        if business_id:
            payload["business_id"] = business_id
        if idempotency_key:
            payload["idempotency_key"] = idempotency_key
        # If auth headers contain Bearer token, pass it through as auth_token
        if auth_headers:
            auth = auth_headers.get("Authorization") or auth_headers.get("authorization")
            if auth and auth.startswith("Bearer "):
                payload["auth_token"] = auth.split(" ", 1)[1]

        return await adapter.create_or_update_draft(payload)
    except Exception as e:
        logger.exception("create_cart_draft error: %s", e)
        return {}


async def add_cart_items(
    cart_id: str,
    items: list[Dict[str, Any]],
    *,
    idempotency_key: Optional[str] = None,
    auth_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Add items to a cart. Items are list of dicts with keys: variant_id, quantity, unit_price."""
    try:
        adapter = AdapterFactory.get_cart_order_adapter()
        # Build payload for adapter.create_or_update_draft which accepts draft_id and items
        payload: Dict[str, Any] = {"draft_id": cart_id, "items": items}
        if idempotency_key:
            payload["idempotency_key"] = idempotency_key
        if auth_headers:
            auth = auth_headers.get("Authorization") or auth_headers.get("authorization")
            if auth and auth.startswith("Bearer "):
                payload["auth_token"] = auth.split(" ", 1)[1]

        # Adapter will create/update the draft and return the draft object
        return await adapter.create_or_update_draft(payload)
    except Exception as e:
        logger.exception("add_cart_items error: %s", e)
        return {"status": "error", "error": str(e)}


async def remove_cart_item(cart_id: str, item_id: str) -> bool:
    """Remove an item from cart (DELETE /cart/{cart_id}/remove/{item_id})."""
    try:
        adapter = AdapterFactory.get_cart_order_adapter()
        payload = {"draft_id": cart_id, "item_id": item_id}
        # Adapter exposes update/remove via create_or_update_draft when items include negative qty or explicit remove
        # Use adapter method if available; fallback to adapter's HTTP session removal if needed
        if hasattr(adapter, "remove_item"):
            return await adapter.remove_item(payload)
        # fallback: call create_or_update_draft with items marked for removal
        payload = {"draft_id": cart_id, "items": [{"item_id": item_id, "action": "remove"}]}
        await adapter.create_or_update_draft(payload)
        return True
    except Exception as e:
        logger.exception("remove_cart_item error: %s", e)
        return False


async def send_notification_receipt(
    db_session: Optional[Any],
    *,
    request_id: str,
    status: str,
    channel: Optional[str] = "whatsapp",
    to: Optional[str] = None,
    business_id: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
    reliable: bool = True,
    correlation_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Send a notification receipt to the Notification service.

    - If `reliable` is True this will enqueue an Outbox row (requires `db_session`).
    - If `reliable` is False this will POST directly to the Notification `/notification/receipts` endpoint.

    `request_id` is the notification's request id (notification record id).
    Returns a dict with `status` and optional `response`/`error`.
    """
    payload = {
        "request_id": request_id,
        "status": status,
        "channel": channel,
        "to": to,
        "business_id": business_id,
        "meta": meta or {},
    }

    base = os.getenv("NOTIFICATION_URL") or "http://notification:8570"
    base = base.rstrip("/")
    target = f"{base}/notification/receipts"

    try:
        return await deliver(payload, target, reliable=reliable, db_session=db_session, correlation_id=correlation_id, idempotency_key=idempotency_key)
    except Exception as e:
        logger.exception("send_notification_receipt failed: %s", e)
        return {"status": "error", "error": str(e)}


async def get_carts_by_session(session_id: str) -> list[Dict[str, Any]]:
    """Fetch carts for a session (GET /cart/session/{session_id})."""
    try:
        adapter = AdapterFactory.get_cart_order_adapter()
        # Adapter should expose a method to fetch carts by session
        if hasattr(adapter, "get_carts_by_session"):
            return await adapter.get_carts_by_session(session_id)
        # fallback to HTTP via adapter
        client = await adapter._get_session()
        async with client.get(f"{adapter.base_url}/cart/session/{session_id}") as resp:
            if resp.status == 200:
                return await resp.json()
            return []
    except Exception as e:
        logger.exception("get_carts_by_session error: %s", e)
        return []


async def delete_cart(cart_id: str) -> bool:
    """Delete a cart by removing all its items (no direct delete endpoint)."""
    try:
        # Fetch cart items via session endpoint not directly available; caller should
        # provide session_id if available. As a fallback, attempt to remove items
        # by fetching cart via GET /cart/session and matching cart_id.
        adapter = AdapterFactory.get_cart_order_adapter()
        # If adapter has a helper to delete/clear cart, use it
        if hasattr(adapter, "clear_cart"):
            return await adapter.clear_cart(cart_id)
        # Otherwise, best-effort: fetch draft and remove each item
        if hasattr(adapter, "get_draft"):
            draft = await adapter.get_draft(cart_id)
            items = draft.get("items", []) if draft else []
            for it in items:
                await remove_cart_item(cart_id, it.get("item_id") or it.get("id"))
            return True
        logger.warning("delete_cart: no clear/delete adapter method available for cart %s", cart_id)
        return False
    except Exception as e:
        logger.exception("delete_cart error: %s", e)
        return False


async def checkout_cart(cart_id: str, *, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
    """Trigger cart checkout (POST /cart/{cart_id}/checkout). Returns CheckoutOut dict."""
    try:
        adapter = AdapterFactory.get_cart_order_adapter()
        payload: Dict[str, Any] = {"draft_id": cart_id}
        if idempotency_key:
            payload["idempotency_key"] = idempotency_key

        # Use adapter reserve/checkout method
        if hasattr(adapter, "reserve_items"):
            return await adapter.reserve_items(payload)
        # fallback to HTTP
        client = await adapter._get_session()
        headers = {}
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key
        async with client.post(f"{adapter.base_url}/cart/{cart_id}/checkout", headers=headers) as resp:
            if resp.status in (200, 201):
                return await resp.json()
            text = await resp.text()
            logger.error("checkout_cart failed %s %s", resp.status, text)
            return {"status": "FAILED", "reason": text}
    except Exception as e:
        logger.exception("checkout_cart error: %s", e)
        return {"status": "FAILED", "reason": str(e)}


# ----- Order + Delivery helpers -----


async def get_order(order_id: str, auth_headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Fetch order by id from Order-Delivery service."""
    try:
        adapter = AdapterFactory.get_cart_order_adapter()
        base = getattr(adapter, "order_base_url", None) or adapter.base_url
        if not base:
            # fallback to delivery adapter
            delivery = AdapterFactory.get_delivery_adapter()
            base = getattr(delivery, "base_url", None)
            client = await delivery._get_session()
        else:
            client = await adapter._get_session()

        headers = {}
        if auth_headers:
            auth = auth_headers.get("Authorization") or auth_headers.get("authorization")
            if auth:
                headers["Authorization"] = auth

        async with client.get(f"{base.rstrip('/')}/orders/{order_id}", headers=headers) as resp:
            if resp.status == 200:
                return await resp.json()
            return {}
    except Exception as e:
        logger.exception("get_order error: %s", e)
        return {}


async def create_order(payload: Dict[str, Any], *, idempotency_key: Optional[str] = None, auth_headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Create an order via Order-Delivery service (POST /orders/create)."""
    try:
        adapter = AdapterFactory.get_cart_order_adapter()
        base = getattr(adapter, "order_base_url", None) or adapter.base_url
        if not base:
            return {"status": "FAILED", "reason": "ORDER_SERVICE_NOT_CONFIGURED"}
        client = await adapter._get_session()
        headers = {}
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key
        if auth_headers:
            auth = auth_headers.get("Authorization") or auth_headers.get("authorization")
            if auth:
                headers["Authorization"] = auth

        async with client.post(f"{base.rstrip('/')}/orders/create", json=payload, headers=headers) as resp:
            if resp.status in (200, 201):
                return await resp.json()
            text = await resp.text()
            logger.error("create_order failed %s %s", resp.status, text)
            return {"status": "FAILED", "reason": text}
    except Exception as e:
        logger.exception("create_order error: %s", e)
        return {"status": "FAILED", "reason": str(e)}


async def initiate_order_payment(order_id: str, phone_number: str, provider: Optional[str] = None, *, idempotency_key: Optional[str] = None, auth_headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Call Order-Delivery to initiate payment for `order_id` (POST /orders/{order_id}/initiate_payment)."""
    try:
        adapter = AdapterFactory.get_cart_order_adapter()
        base = getattr(adapter, "order_base_url", None) or adapter.base_url
        if not base:
            return {"status": "FAILED", "reason": "ORDER_SERVICE_NOT_CONFIGURED"}
        client = await adapter._get_session()
        headers = {}
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key
        if auth_headers:
            auth = auth_headers.get("Authorization") or auth_headers.get("authorization")
            if auth:
                headers["Authorization"] = auth

        body = {"phone_number": phone_number, "provider": provider}
        async with client.post(f"{base.rstrip('/')}/orders/{order_id}/initiate_payment", json=body, headers=headers) as resp:
            if resp.status in (200, 201):
                return await resp.json()
            text = await resp.text()
            logger.error("initiate_order_payment failed %s %s", resp.status, text)
            return {"status": "FAILED", "reason": text}
    except Exception as e:
        logger.exception("initiate_order_payment error: %s", e)
        return {"status": "FAILED", "reason": str(e)}


async def mark_order_paid(order_id: str, auth_headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Mark an order as paid via Order-Delivery (POST /orders/{order_id}/mark_paid)."""
    try:
        adapter = AdapterFactory.get_cart_order_adapter()
        base = getattr(adapter, "order_base_url", None) or adapter.base_url
        if not base:
            return {"status": "FAILED", "reason": "ORDER_SERVICE_NOT_CONFIGURED"}
        client = await adapter._get_session()
        headers = {}
        if auth_headers:
            auth = auth_headers.get("Authorization") or auth_headers.get("authorization")
            if auth:
                headers["Authorization"] = auth

        async with client.post(f"{base.rstrip('/')}/orders/{order_id}/mark_paid", headers=headers) as resp:
            if resp.status in (200, 201):
                return await resp.json()
            text = await resp.text()
            logger.error("mark_order_paid failed %s %s", resp.status, text)
            return {"status": "FAILED", "reason": text}
    except Exception as e:
        logger.exception("mark_order_paid error: %s", e)
        return {"status": "FAILED", "reason": str(e)}


async def confirm_order_by_business(order_id: str, payload: Dict[str, Any], auth_headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Business/MSME confirm an order (POST /orders/{order_id}/confirm)."""
    try:
        adapter = AdapterFactory.get_cart_order_adapter()
        base = getattr(adapter, "order_base_url", None) or adapter.base_url
        if not base:
            return {"status": "FAILED", "reason": "ORDER_SERVICE_NOT_CONFIGURED"}
        client = await adapter._get_session()
        headers = {}
        if auth_headers:
            auth = auth_headers.get("Authorization") or auth_headers.get("authorization")
            if auth:
                headers["Authorization"] = auth

        async with client.post(f"{base.rstrip('/')}/orders/{order_id}/confirm", json=payload, headers=headers) as resp:
            if resp.status in (200, 201):
                return await resp.json()
            text = await resp.text()
            logger.error("confirm_order_by_business failed %s %s", resp.status, text)
            return {"status": "FAILED", "reason": text}
    except Exception as e:
        logger.exception("confirm_order_by_business error: %s", e)
        return {"status": "FAILED", "reason": str(e)}


async def confirm_delivery(delivery_id: str, delivery_code: str, *, confirmed_by: Optional[str] = None, auth_headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Confirm a delivery by code (POST /delivery/{delivery_id}/confirm)."""
    try:
        # Prefer delivery adapter if configured
        delivery_adapter = AdapterFactory.get_delivery_adapter()
        base = getattr(delivery_adapter, "base_url", None) or ""
        client = await delivery_adapter._get_session()
        headers = {}
        if auth_headers:
            auth = auth_headers.get("Authorization") or auth_headers.get("authorization")
            if auth:
                headers["Authorization"] = auth

        body = {"delivery_code": delivery_code}
        if confirmed_by:
            body["confirmed_by"] = confirmed_by

        async with client.post(f"{base.rstrip('/')}/delivery/{delivery_id}/confirm", json=body, headers=headers) as resp:
            if resp.status in (200, 201):
                return await resp.json()
            text = await resp.text()
            logger.error("confirm_delivery failed %s %s", resp.status, text)
            return {"status": "FAILED", "reason": text}
    except Exception as e:
        logger.exception("confirm_delivery error: %s", e)
        return {"status": "FAILED", "reason": str(e)}


async def select_delivery_location(business_id: str, chosen: Optional[str], auth_headers: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
    """Select and return a canonical delivery location dict for `business_id`.

    `chosen` may be an id, name, label, or an address string. Returns the matching
    location dict from MSME (including fee fields) or None if not found.
    """
    if not chosen:
        return None
    try:
        msme = AdapterFactory.get_msme_adapter()
        locations = await msme.fetch_business_delivery_locations(business_id)
        for loc in locations:
            # match by candidate id/name/label/address
            if str(loc.get("id")) == str(chosen) or str(loc.get("name")) == str(chosen) or str(loc.get("label")) == str(chosen) or str(loc.get("address") or "") == str(chosen):
                return loc
        return None
    except Exception as e:
        logger.exception("select_delivery_location error: %s", e)
        return None


async def set_order_delivery_location(order_id: str, chosen: str, auth_headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Call Order-Delivery to set/change the delivery location for `order_id`.

    Uses the DeliveryServiceAdapter `set_order_delivery_location` method.
    """
    try:
        adapter = AdapterFactory.get_delivery_adapter()
        token = None
        if auth_headers:
            token = auth_headers.get("Authorization") or auth_headers.get("authorization")
            if token and token.startswith("Bearer "):
                token = token.split(" ", 1)[1]
        return await adapter.set_order_delivery_location(order_id, chosen, auth_token=token)
    except Exception as e:
        logger.exception("set_order_delivery_location helper error: %s", e)
        return {"status": "FAILED", "reason": str(e)}


async def set_order_payment_method(order_id: str, phone_number: str, auth_headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Set or update payment phone for an order via Order-Delivery service.

    Returns the JSON response from Order-Delivery or a failure dict.
    """
    try:
        # Prefer delivery adapter which targets Order-Delivery service directly
        delivery = AdapterFactory.get_delivery_adapter()
        token = None
        if auth_headers:
            token = auth_headers.get("Authorization") or auth_headers.get("authorization")
            if token and token.startswith("Bearer "):
                token = token.split(" ", 1)[1]

        # Use delivery adapter if configured (calls ORDER_DELIVERY_URL)
        if getattr(delivery, "use_http", False):
            return await delivery.set_order_payment_method(order_id, phone_number, auth_token=token)

        # Fallback: use cart/order adapter which may proxy to order service
        adapter = AdapterFactory.get_cart_order_adapter()
        base = getattr(adapter, "order_base_url", None) or adapter.base_url
        if not base:
            return {"status": "FAILED", "reason": "ORDER_SERVICE_NOT_CONFIGURED"}
        client = await adapter._get_session()
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if auth_headers:
            auth = auth_headers.get("Authorization") or auth_headers.get("authorization")
            if auth:
                headers["Authorization"] = auth

        body = {"phone_number": phone_number}
        async with client.put(f"{base.rstrip('/')}/orders/{order_id}/payment_method", json=body, headers=headers) as resp:
            if resp.status in (200, 201):
                return await resp.json()
            text = await resp.text()
            logger.error("set_order_payment_method failed %s %s", resp.status, text)
            return {"status": "FAILED", "reason": text}
    except Exception as e:
        logger.exception("set_order_payment_method helper error: %s", e)
        return {"status": "FAILED", "reason": str(e)}
