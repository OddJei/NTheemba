from __future__ import annotations

from typing import Any

from ..oob_store import OOBStore


async def remove_item(*, store: OOBStore, session_id: str, product_name: str, event_id: str | None = None) -> tuple[dict[str, Any], int]:
    def _upd(oob: dict[str, Any]) -> dict[str, Any]:
        oob = dict(oob)
        cart = dict(oob.get("cart") or {})
        items = list(cart.get("items") or [])
        new_items = [i for i in items if (i.get("product_name") or "").lower() != product_name.lower()]
        cart["items"] = new_items
        oob["cart"] = cart
        if event_id:
            oob["last_event_id"] = event_id
        oob["last_node_executed"] = "cart.remove_item"
        return oob

    return await OOBStore().cas_update(session_id, _upd)
