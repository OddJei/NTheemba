from __future__ import annotations

from typing import Any, Tuple

from ..oob_store import OOBStore


async def confirm_order_gate(*, store: OOBStore, session_id: str, event_id: str | None = None, raw_text: str | None = None, ice_client=None) -> Tuple[dict[str, Any], int]:
    """Strict confirm gate: requires exact phrase 'CONFIRM ORDER' (case-insensitive exact match)

    On success calls ICE to create the order and persists `oob.meta.order_id` and `oob.cart.status = 'order_created'`.
    Requires an async `ice_client.create_order(session_id, oob_ref, event_id)` method.
    """

    if raw_text is None or (raw_text.strip().upper() != "CONFIRM ORDER"):
        def _bad(oob: dict[str, Any]) -> dict[str, Any]:
            oob = dict(oob)
            oob["last_validation_error"] = "confirm_phrase_required"
            oob["last_node_executed"] = "confirm_order_gate"
            return oob

        return await store.cas_update(session_id, _bad)

    if ice_client is None:
        raise ValueError("ice_client required for order creation")

    try:
        resp = await ice_client.create_order(session_id=session_id, oob_ref=f"oob:{session_id}", event_id=event_id)
    except Exception:
        def _err(oob: dict[str, Any]) -> dict[str, Any]:
            oob = dict(oob)
            oob["last_validation_error"] = "order_create_failed"
            oob["last_node_executed"] = "confirm_order_gate"
            return oob

        return await store.cas_update(session_id, _err)

    order_id = resp.get("order_id") or resp.get("id")
    status = resp.get("status") or "created"

    def _upd(oob: dict[str, Any]) -> dict[str, Any]:
        oob = dict(oob)
        meta = dict(oob.get("meta") or {})
        meta["order_id"] = order_id
        meta["order_status"] = status
        oob["meta"] = meta
        cart = dict(oob.get("cart") or {})
        cart["status"] = "order_created"
        oob["cart"] = cart
        if event_id:
            oob["last_event_id"] = event_id
        oob["last_node_executed"] = "confirm_order_gate"
        return oob

    return await store.cas_update(session_id, _upd)
