from __future__ import annotations

from typing import Any, Tuple

from ..oob_store import OOBStore


async def initiate_refund(*, store: OOBStore, session_id: str, event_id: str | None = None, raw_text: str | None = None, ice_client=None) -> Tuple[dict[str, Any], int]:
    """Record a refund request: call ICE to log the refund and notify admin.

    If `raw_text` contains a reason we use it; otherwise the caller should ask for reason first.
    Updates `oob.meta.refund_request_id`, `oob.meta.refund_status`, and `oob.meta.refund_reason`.
    Requires `ice_client.request_refund` and `ice_client.notify_admin`.
    """

    if ice_client is None:
        raise ValueError("ice_client required for refund request")

    # fetch current OOB to find order_id
    try:
        oob_current, _ = await store.get_oob(session_id)
    except Exception:
        oob_current = {}

    meta = oob_current.get("meta") or {}
    order_id = meta.get("order_id")
    reason = (raw_text or "").strip() or None

    if not order_id:
        def _err(oob: dict[str, Any]) -> dict[str, Any]:
            oob = dict(oob)
            oob["last_validation_error"] = "order_id_missing"
            oob["last_node_executed"] = "initiate_refund"
            if event_id:
                oob["last_event_id"] = event_id
            return oob

        return await store.cas_update(session_id, _err)

    # Attempt to record refund in ICE
    try:
        resp = await ice_client.request_refund(session_id=session_id, order_id=order_id, reason=reason, event_id=event_id)
    except Exception:
        def _err(oob: dict[str, Any]) -> dict[str, Any]:
            oob = dict(oob)
            oob["last_validation_error"] = "refund_request_failed"
            oob["last_node_executed"] = "initiate_refund"
            if event_id:
                oob["last_event_id"] = event_id
            return oob

        return await store.cas_update(session_id, _err)

    refund_id = resp.get("refund_id") or resp.get("id")
    status = resp.get("status") or "requested"

    # notify admin about the refund so they can investigate/approve
    try:
        subject = f"Refund request: order {order_id}"
        message = f"Refund requested for order {order_id}. Reason: {reason or 'not provided'}. Refund id: {refund_id}."
        await ice_client.notify_admin(session_id=session_id, subject=subject, message=message, event_id=event_id)
    except Exception:
        # notification failure should not block the refund creation; log via OOB
        pass

    def _upd(oob: dict[str, Any]) -> dict[str, Any]:
        oob = dict(oob)
        meta = dict(oob.get("meta") or {})
        if refund_id:
            meta["refund_request_id"] = refund_id
        meta["refund_status"] = status
        if reason:
            meta["refund_reason"] = reason
        oob["meta"] = meta
        oob["last_node_executed"] = "initiate_refund"
        if event_id:
            oob["last_event_id"] = event_id
        return oob

    return await store.cas_update(session_id, _upd)
