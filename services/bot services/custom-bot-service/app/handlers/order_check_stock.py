from __future__ import annotations

from typing import Any, Tuple

from ..oob_store import OOBStore


async def check_stock(*, store: OOBStore, session_id: str, event_id: str | None = None, ice_client=None) -> Tuple[dict[str, Any], int]:
    """Call ICE to validate/reserve stock for all cart items (authoritative).

    This is an authoritative operation and requires `ice_client`. If ICE is not
    configured, the handler raises `ValueError` so the runtime can fall back.
    """

    if ice_client is None:
        raise ValueError("ICE client not configured")

    # Ensure OOB exists
    oob, ver = await store.create_default_if_missing(session_id)

    cart = (oob.get("cart") or {})
    items = list(cart.get("items") or [])

    # If no items, record a friendly validation error locally
    if not items:
        def _upd_empty(o: dict[str, Any]) -> dict[str, Any]:
            o = dict(o)
            o["last_validation_error"] = "no_items_for_stock_check"
            o["last_node_executed"] = "order.check_stock"
            return o

        return await store.cas_update(session_id, _upd_empty)

    # Ask ICE to verify/reserve stock for the items
    resp = await ice_client.check_stock(session_id=session_id, items=items)

    def _upd(o: dict[str, Any]) -> dict[str, Any]:
        o = dict(o)
        meta = dict(o.get("meta") or {})
        meta["stock_check"] = resp
        o["meta"] = meta
        # Determine if any item is unavailable
        unavailable = False
        for it in (resp.get("items") or []):
            if not it.get("available", False):
                unavailable = True
                break

        if unavailable:
            o["last_validation_error"] = "out_of_stock"
        else:
            o.pop("last_validation_error", None)

        o["last_node_executed"] = "order.check_stock"
        return o

    return await store.cas_update(session_id, _upd)
