from __future__ import annotations

from typing import Any, Tuple

from ..oob_store import OOBStore


async def confirm_cart(*, store: OOBStore, session_id: str, event_id: str | None = None) -> Tuple[dict[str, Any], int]:
    """Validate the cart for ordering and mark it ready for review.

    This is intentionally ICE-free: it only validates local OOB shape (presence of items,
    sane quantities). Authoritative pricing/stock checks are left to `order.calculate_total`
    or downstream ICE calls.
    """

    def _upd(oob: dict[str, Any]) -> dict[str, Any]:
        oob = dict(oob)
        cart = dict(oob.get("cart") or {})
        items = list(cart.get("items") or [])

        # Basic validations
        if not items:
            oob["last_validation_error"] = "no_items"
            oob["last_node_executed"] = "order.confirm_cart"
            # keep cart.status as-is
            return oob

        # Ensure quantities are sane
        bad_qty = False
        for it in items:
            try:
                q = int(it.get("quantity") or 0)
            except Exception:
                q = 0
            if q <= 0:
                bad_qty = True
                break

        if bad_qty:
            oob["last_validation_error"] = "invalid_quantity"
            oob["last_node_executed"] = "order.confirm_cart"
            return oob

        # Passed basic checks: mark ready for review
        cart["status"] = "ready_for_review"
        oob["cart"] = cart
        if event_id:
            oob["last_event_id"] = event_id
        oob["last_node_executed"] = "order.confirm_cart"
        # clear previous validation error if any
        oob.pop("last_validation_error", None)
        return oob

    return await store.cas_update(session_id, _upd)
