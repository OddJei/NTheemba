from __future__ import annotations

from typing import Any, Dict

from ..oob_store import OOBStore
from ..resolver import resolve_required_blobs


async def select_product(
    *,
    store: OOBStore,
    session_id: str,
    product_id: str | None = None,
    product_name: str | None = None,
    event_id: str | None = None,
    ice_client=None,
) -> tuple[dict[str, Any], int]:
    """Persist selected product into OOB.meta.selected_product. Optionally hydrate product details from ICE."""

    def _upd(oob: dict[str, Any]) -> dict[str, Any]:
        oob = dict(oob)
        meta = dict(oob.get("meta") or {})
        sel = {"id": product_id, "name": product_name}
        meta["selected_product"] = sel
        oob["meta"] = meta
        if event_id:
            oob["last_event_id"] = event_id
        oob["last_node_executed"] = "browse_catalogue.select_product"
        return oob

    new_oob, ver = await store.cas_update(session_id, _upd)

    # Optionally hydrate authoritative product blob into cache via resolver
    if ice_client is not None and product_id:
        try:
            await resolve_required_blobs(
                store=store, session_id=session_id, required_blobs=[f"product:{product_id}"], ice_client=ice_client, event_id=event_id
            )
        except Exception:
            pass

    return new_oob, ver
