from __future__ import annotations

from typing import Any

from ..oob_store import OOBStore


async def review_order(*, store: OOBStore, session_id: str) -> dict[str, Any]:
    """Read-only order review: summarize cart items, totals, and required fields.

    Returns a dict with `oob`, `oob_ver`, `items_count`, `totals`, and `ready_to_confirm`.
    """

    oob, ver = await store.get_oob(session_id)
    cart = oob.get("cart") or {}
    items = list(cart.get("items") or [])
    totals = cart.get("totals") or {}

    items_count = len(items) if isinstance(items, list) else 0

    # Basic readiness: must have items and authoritative totals (grand_total present)
    ready_to_confirm = items_count > 0 and isinstance(totals, dict) and totals.get("grand_total") is not None

    return {
        "oob": oob,
        "oob_ver": ver,
        "items_count": items_count,
        "totals": totals,
        "ready_to_confirm": ready_to_confirm,
        "items": items,
    }
