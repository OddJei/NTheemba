from __future__ import annotations

from typing import Any

from ..oob_store import OOBStore


async def view_cart(*, store: OOBStore, session_id: str) -> dict[str, Any]:
    oob, ver = await store.get_oob(session_id)
    cart = oob.get("cart") or {}
    items = cart.get("items") or []
    totals = cart.get("totals") or {}
    return {"oob": oob, "oob_ver": ver, "items_count": len(items), "totals": totals}
