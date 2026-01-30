from __future__ import annotations

from typing import Any

from ..oob_store import OOBStore


async def clear_cart(*, store: OOBStore, session_id: str, event_id: str | None = None) -> tuple[dict[str, Any], int]:
    def _upd(oob: dict[str, Any]) -> dict[str, Any]:
        oob = dict(oob)
        oob["cart"] = {"items": [], "totals": {"subtotal": 0, "grand_total": 0}, "status": "building", "cart_version": 1}
        if event_id:
            oob["last_event_id"] = event_id
        oob["last_node_executed"] = "cart.clear"
        return oob

    return await OOBStore().cas_update(session_id, _upd)
