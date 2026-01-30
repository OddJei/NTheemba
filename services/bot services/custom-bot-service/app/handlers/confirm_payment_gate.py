from __future__ import annotations

from typing import Any, Tuple

from ..oob_store import OOBStore


async def confirm_payment_gate(*, store: OOBStore, session_id: str, event_id: str | None = None, raw_text: str | None = None, ice_client=None) -> Tuple[dict[str, Any], int]:
    """Strict confirm gate: requires exact phrase 'CONFIRM PAYMENT' (case-insensitive exact match)

    On success calls ICE to trigger payment and persists `oob.meta.payment_id` and `oob.meta.payment_status`.
    Requires an async `ice_client.trigger_payment(session_id, oob_ref, event_id)` method.
    """

    if raw_text is None or (raw_text.strip().upper() != "CONFIRM PAYMENT"):
        def _bad(oob: dict[str, Any]) -> dict[str, Any]:
            oob = dict(oob)
            oob["last_validation_error"] = "confirm_phrase_required"
            oob["last_node_executed"] = "confirm_payment_gate"
            return oob

        return await store.cas_update(session_id, _bad)

    if ice_client is None:
        raise ValueError("ice_client required for payment trigger")

    try:
        resp = await ice_client.trigger_payment(session_id=session_id, oob_ref=f"oob:{session_id}", event_id=event_id)
    except Exception:
        def _err(oob: dict[str, Any]) -> dict[str, Any]:
            oob = dict(oob)
            oob["last_validation_error"] = "payment_trigger_failed"
            oob["last_node_executed"] = "confirm_payment_gate"
            return oob

        return await store.cas_update(session_id, _err)

    payment_id = resp.get("payment_id") or resp.get("id")
    status = resp.get("status") or "initiated"

    def _upd(oob: dict[str, Any]) -> dict[str, Any]:
        oob = dict(oob)
        meta = dict(oob.get("meta") or {})
        meta["payment_id"] = payment_id
        meta["payment_status"] = status
        oob["meta"] = meta
        cart = dict(oob.get("cart") or {})
        # set cart status depending on payment state
        if status.lower() in ("paid", "success"):
            cart["status"] = "paid"
        else:
            cart["status"] = "payment_initiated"
        oob["cart"] = cart
        if event_id:
            oob["last_event_id"] = event_id
        oob["last_node_executed"] = "confirm_payment_gate"
        return oob

    return await store.cas_update(session_id, _upd)
