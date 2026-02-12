from __future__ import annotations

from typing import Any, Tuple

from ..oob_store import OOBStore


async def verify_payment_status(*, store: OOBStore, session_id: str, event_id: str | None = None, ice_client=None) -> Tuple[dict[str, Any], int]:
    """Check payment status via ICE and persist result into OOB.

    Requires `ice_client.get_payment_status(payment_id=...)`.
    """

    def _no_payment(oob: dict[str, Any]) -> dict[str, Any]:
        oob = dict(oob)
        oob["last_validation_error"] = "no_payment_id"
        oob["last_node_executed"] = "payment_verify_status"
        return oob

    # read current oob to find payment_id
    cur_oob, _ = await store.get_oob(session_id)
    payment_id = (cur_oob.get("meta") or {}).get("payment_id")
    if not payment_id:
        return await store.cas_update(session_id, _no_payment)

    if ice_client is None:
        raise ValueError("ice_client required for checking payment status")

    try:
        resp = await ice_client.get_payment_status(payment_id=payment_id, session_id=session_id)
    except Exception:
        def _err(oob: dict[str, Any]) -> dict[str, Any]:
            oob = dict(oob)
            oob["last_validation_error"] = "payment_status_failed"
            oob["last_node_executed"] = "payment_verify_status"
            return oob

        return await store.cas_update(session_id, _err)

    status = resp.get("status") or resp.get("payment_status") or "unknown"
    pid = resp.get("payment_id") or payment_id

    def _upd(oob: dict[str, Any]) -> dict[str, Any]:
        oob = dict(oob)
        meta = dict(oob.get("meta") or {})
        meta["payment_id"] = pid
        meta["payment_status"] = status
        oob["meta"] = meta
        cart = dict(oob.get("cart") or {})
        if status.lower() in ("paid", "success"):
            cart["status"] = "paid"
        else:
            cart["status"] = "payment_initiated"
        oob["cart"] = cart
        if event_id:
            oob["last_event_id"] = event_id
        oob["last_node_executed"] = "payment_verify_status"
        return oob

    return await store.cas_update(session_id, _upd)
