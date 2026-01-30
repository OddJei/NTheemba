from __future__ import annotations

from typing import Any, Tuple

from ..oob_store import OOBStore


async def choose_location(
    *,
    store: OOBStore,
    session_id: str,
    address: dict | None = None,
    pickup_location: dict | None = None,
    event_id: str | None = None,
    ice_client=None,
) -> Tuple[dict[str, Any], int]:
    """Set delivery address or pickup location into the OOB.

    This is intentionally cache-first and local: authoritative address
    normalization should be performed by ICE if needed.
    """

    def _upd(oob: dict[str, Any]) -> dict[str, Any]:
        oob = dict(oob)
        if address:
            oob["delivery"] = dict(oob.get("delivery") or {})
            oob["delivery"]["address"] = address
        if pickup_location:
            meta = dict(oob.get("meta") or {})
            meta["pickup_location"] = pickup_location
            oob["meta"] = meta

        oob["last_node_executed"] = "fulfillment.choose_location"
        oob.pop("last_validation_error", None)
        return oob

    return await store.cas_update(session_id, _upd)
