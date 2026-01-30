from __future__ import annotations

from typing import Any, Tuple

from ..oob_store import OOBStore


async def track_click(*, store: OOBStore, session_id: str, event_id: str | None = None, ice_client=None) -> Tuple[dict[str, Any], int]:
    """Ask ICE to record a campaign click/event for the affiliate code stored in OOB.meta.

    This is optional: if ICE is not configured the handler raises ValueError so the
    runtime can handle gracefully.
    """

    if ice_client is None:
        raise ValueError("ICE client not configured")

    oob, ver = await store.create_default_if_missing(session_id)
    meta = oob.get("meta") or {}
    code = meta.get("affiliate_code")
    source = meta.get("affiliate_source")

    if not code:
        # Nothing to track
        def _upd_noop(o: dict[str, Any]) -> dict[str, Any]:
            o = dict(o)
            o["last_node_executed"] = "affiliate.track_click"
            return o

        return await store.cas_update(session_id, _upd_noop)

    # Call ICE to record click
    resp = await ice_client.track_affiliate_click(session_id=session_id, affiliate_code=code, source=source, event_id=event_id)

    def _upd(o: dict[str, Any]) -> dict[str, Any]:
        o = dict(o)
        meta = dict(o.get("meta") or {})
        meta["affiliate_last_track"] = resp
        o["meta"] = meta
        o["last_node_executed"] = "affiliate.track_click"
        return o

    return await store.cas_update(session_id, _upd)
