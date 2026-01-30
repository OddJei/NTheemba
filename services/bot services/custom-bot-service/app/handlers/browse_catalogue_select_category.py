from __future__ import annotations

from typing import Any

from ..oob_store import OOBStore


async def select_category(
    *,
    store: OOBStore,
    session_id: str,
    category_id: str | None = None,
    category_name: str | None = None,
    event_id: str | None = None,
) -> tuple[dict[str, Any], int]:
    """Select a category into OOB.meta.selected_category (cache-first).

    Returns updated (oob, version).
    """

    def _upd(oob: dict[str, Any]) -> dict[str, Any]:
        oob = dict(oob)
        meta = dict(oob.get("meta") or {})
        if category_id:
            meta["selected_category"] = {"id": category_id, "name": category_name}
        else:
            meta["selected_category"] = {"id": None, "name": category_name}
        oob["meta"] = meta
        if event_id:
            oob["last_event_id"] = event_id
        oob["last_node_executed"] = "browse_catalogue.select_category"
        return oob

    return await store.cas_update(session_id, _upd)
