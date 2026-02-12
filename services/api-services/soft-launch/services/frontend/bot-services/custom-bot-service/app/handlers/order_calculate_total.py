from __future__ import annotations

from typing import Any, Tuple

from ..oob_store import OOBStore


async def calculate_total(*, store: OOBStore, session_id: str, event_id: str | None = None, ice_client=None) -> Tuple[dict[str, Any], int]:
    """Call ICE to price the cart and persist totals into OOB.

    - `ice_client` is expected to provide an async `price_cart(session_id, oob_ref, event_id=None)` method.
    - On success: writes `oob.cart.totals` and sets `oob.cart.status = 'priced'`.
    - On failure: writes `oob.last_validation_error = 'pricing_failed'` and `last_node_executed`.
    """

    if ice_client is None:
        raise ValueError("ice_client required for authoritative pricing")

    try:
        pricing = await ice_client.price_cart(session_id=session_id, oob_ref=f"oob:{session_id}", event_id=event_id)
    except Exception:
        def _err(oob: dict[str, Any]) -> dict[str, Any]:
            oob = dict(oob)
            oob["last_validation_error"] = "pricing_failed"
            oob["last_node_executed"] = "order.calculate_total"
            return oob

        return await store.cas_update(session_id, _err)

    def _upd(oob: dict[str, Any]) -> dict[str, Any]:
        oob = dict(oob)
        cart = dict(oob.get("cart") or {})
        cart["totals"] = pricing
        cart["status"] = "priced"
        oob["cart"] = cart
        if event_id:
            oob["last_event_id"] = event_id
        oob["last_node_executed"] = "order.calculate_total"
        # clear previous validation errors
        oob.pop("last_validation_error", None)
        return oob

    return await store.cas_update(session_id, _upd)
