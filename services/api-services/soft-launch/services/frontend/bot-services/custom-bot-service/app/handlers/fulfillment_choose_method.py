from __future__ import annotations

from typing import Any, Tuple

from ..oob_store import OOBStore


async def choose_method(*, store: OOBStore, session_id: str, method: str | None = None, details: dict[str, Any] | None = None, event_id: str | None = None, ice_client=None) -> Tuple[dict[str, Any], int]:
    """Set the fulfillment method (delivery/pickup) in OOB.

    If `ice_client` is provided, the handler will call `ice_client.validate_fulfillment_method`
    to ensure the chosen method and details are acceptable (cache-first pattern).
    """

    def _missing(oob: dict[str, Any]) -> dict[str, Any]:
        oob = dict(oob)
        oob["last_validation_error"] = "fulfillment_method_required"
        oob["last_node_executed"] = "fulfillment_choose_method"
        return oob

    if not method:
        return await store.cas_update(session_id, _missing)

    # Optionally validate via ICE
    if ice_client is not None:
        try:
            ok = await ice_client.validate_fulfillment_method(session_id=session_id, method=method, details=details or {})
            if not ok or (isinstance(ok, dict) and ok.get("valid") is False):
                def _invalid(oob: dict[str, Any]) -> dict[str, Any]:
                    oob = dict(oob)
                    oob["last_validation_error"] = "fulfillment_method_invalid"
                    oob["last_node_executed"] = "fulfillment_choose_method"
                    return oob

                return await store.cas_update(session_id, _invalid)
        except Exception:
            def _err(oob: dict[str, Any]) -> dict[str, Any]:
                oob = dict(oob)
                oob["last_validation_error"] = "fulfillment_validation_failed"
                oob["last_node_executed"] = "fulfillment_choose_method"
                return oob

            return await store.cas_update(session_id, _err)

    # Persist selection
    def _upd(oob: dict[str, Any]) -> dict[str, Any]:
        oob = dict(oob)
        fulfillment = dict(oob.get("fulfillment") or {})
        fulfillment["method"] = method
        if details:
            fulfillment["details"] = details
        oob["fulfillment"] = fulfillment
        if event_id:
            oob["last_event_id"] = event_id
        oob["last_node_executed"] = "fulfillment_choose_method"
        return oob

    return await store.cas_update(session_id, _upd)
