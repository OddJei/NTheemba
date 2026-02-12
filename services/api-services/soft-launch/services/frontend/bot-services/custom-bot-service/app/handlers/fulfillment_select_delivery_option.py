from __future__ import annotations

from typing import Any, Tuple

from ..oob_store import OOBStore


async def select_delivery_option(
    *,
    store: OOBStore,
    session_id: str,
    method: str | None = None,
    details: dict | None = None,
    event_id: str | None = None,
    ice_client=None,
) -> Tuple[dict[str, Any], int]:
    """Set fulfillment type (`delivery` or `pickup`) and optional details.

    This is a local OOB update (ICE not required). Handlers that need authoritative
    validation (e.g., address normalization) should call ICE separately.
    """

    def _upd(oob: dict[str, Any]) -> dict[str, Any]:
        oob = dict(oob)
        ful = dict(oob.get("fulfillment") or {})
        if method:
            ful["type"] = method
        if details:
            ful_details = dict(ful.get("details") or {})
            ful_details.update(details)
            ful["details"] = ful_details
        oob["fulfillment"] = ful
        oob["last_node_executed"] = "fulfillment.select_delivery_option"
        oob.pop("last_validation_error", None)
        return oob

    return await store.cas_update(session_id, _upd)
