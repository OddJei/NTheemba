from __future__ import annotations

from typing import Any

from ..oob_store import OOBStore


async def add_item(
    *,
    store: OOBStore,
    session_id: str,
    event_id: str | None,
    product_name: str,
    quantity: int,
) -> tuple[dict[str, Any], int]:
    """Add a cart line with (product_name, quantity).

    This is intentionally 'ICE-free': it does not resolve product ids yet.
    Later we can upgrade this handler to call ICE (cache-first) when needed.
    """

    def _upd(oob: dict[str, Any]) -> dict[str, Any]:
        oob = dict(oob)
        cart = dict(oob.get("cart") or {})
        items = list(cart.get("items") or [])

        # Merge by name for now.
        merged = False
        for item in items:
            if isinstance(item, dict) and (item.get("product_name") or "").lower() == product_name.lower():
                item["quantity"] = int(item.get("quantity") or 0) + quantity
                merged = True
                break

        if not merged:
            items.append({"product_name": product_name, "quantity": quantity})

        cart["items"] = items
        cart["status"] = cart.get("status") or "building"
        oob["cart"] = cart
        if event_id:
            oob["last_event_id"] = event_id
        oob["last_node_executed"] = "cart.add_item"
        return oob

    return await store.cas_update(session_id, _upd)
