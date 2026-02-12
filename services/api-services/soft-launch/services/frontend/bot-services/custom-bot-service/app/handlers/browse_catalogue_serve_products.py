from __future__ import annotations

from typing import Any, Dict

from ..oob_store import OOBStore
from ..resolver import resolve_required_blobs


async def serve_products(
    *,
    store: OOBStore,
    session_id: str,
    category_id: str | None = None,
    event_id: str | None = None,
    ice_client=None,
) -> dict[str, Any]:
    """Return products for a category. Cache-first: look in OOB.meta, else ask ICE."""

    oob, ver = await store.create_default_if_missing(session_id)
    meta = oob.get("meta") or {}

    # Determine category from param or OOB
    sel = None
    if category_id:
        sel = category_id
    elif meta.get("selected_category"):
        sel = meta.get("selected_category").get("id") or meta.get("selected_category").get("name")

    products: list[Dict[str, Any]] = []
    if sel:
        key = f"products:category:{sel}"
        try:
            blobs = await resolve_required_blobs(store=store, session_id=session_id, required_blobs=[key], ice_client=ice_client, event_id=event_id)
            data = blobs.get(key) or {}
            products = data.get("products") or []
        except Exception:
            products = []

    if products:
        names = ", ".join([str(p.get("name") or p.get("title") or p.get("id")) for p in products[:5]])
        reply_text = f"Found products: {names}. Which would you like to add to cart?"
    else:
        reply_text = "I don't have products for that category right now. Try a different category or search by name."

    return {"oob": oob, "oob_ver": ver, "reply_text": reply_text, "products": products}
