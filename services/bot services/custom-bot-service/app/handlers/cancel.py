from __future__ import annotations

from ..oob_store import OOBStore


async def cancel_flow(*, store: OOBStore, session_id: str, event_id: str | None = None) -> tuple[dict[str, Any], int]:
    def _upd(oob: dict[str, Any]) -> dict[str, Any]:
        oob = dict(oob)
        # clear draft fields but keep meta
        oob["cart"] = {"items": [], "totals": {"subtotal": 0, "grand_total": 0}, "status": "cancelled", "cart_version": 1}
        oob["last_node_executed"] = "cancel"
        if event_id:
            oob["last_event_id"] = event_id
        return oob

    return await OOBStore().cas_update(session_id, _upd)
