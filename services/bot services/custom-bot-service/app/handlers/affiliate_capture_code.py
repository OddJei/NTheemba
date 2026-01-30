from __future__ import annotations

from typing import Any, Tuple

from ..oob_store import OOBStore


async def capture_code(*, store: OOBStore, session_id: str, affiliate_code: str | None = None, source: str | None = None, payload: dict | None = None, event_id: str | None = None) -> Tuple[dict[str, Any], int]:
    """Capture an affiliate code from payload or explicit param and store in OOB.meta.

    This is a local operation: the bot records the code and source; ICE may be asked
    later to record campaign clicks.
    """

    def _upd(oob: dict[str, Any]) -> dict[str, Any]:
        oob = dict(oob)
        meta = dict(oob.get("meta") or {})

        code = affiliate_code
        src = source

        # Try to derive from payload if not explicitly provided
        if not code and payload:
            try:
                code = payload.get("meta", {}).get("affiliate_code") or payload.get("affiliate_code")
            except Exception:
                code = code
        if not src and payload:
            try:
                src = payload.get("meta", {}).get("affiliate_source")
            except Exception:
                src = src

        if code:
            meta["affiliate_code"] = code
            if src:
                meta["affiliate_source"] = src
            oob["meta"] = meta
            oob["last_node_executed"] = "affiliate.capture_code"
        else:
            oob["last_node_executed"] = "affiliate.capture_code"
        return oob

    return await store.cas_update(session_id, _upd)
