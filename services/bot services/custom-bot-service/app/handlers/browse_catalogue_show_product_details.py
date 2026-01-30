from __future__ import annotations

from typing import Any, Dict

from ..oob_store import OOBStore
from ..resolver import resolve_required_blobs


async def show_product_details(
    *,
    store: OOBStore,
    session_id: str,
    product_id: str | None = None,
    product_name: str | None = None,
    event_id: str | None = None,
    ice_client=None,
) -> dict[str, Any]:
    """Return product details for a given product id or name.

    Cache-first: if ICE is configured and `product_id` is provided, ask ICE for authoritative details.
    Otherwise, attempt to find product info in OOB.meta or return a helpful fallback message.
    """

    oob, ver = await store.create_default_if_missing(session_id)

    product: Dict[str, Any] | None = None

    # Try OOB meta first
    meta = oob.get("meta") or {}
    cached = meta.get("catalog_cache") or {}
    if product_id and cached.get(product_id):
        product = cached.get(product_id)
    elif product_name:
        # search cached entries by name
        lname = product_name.lower()
        for p in (cached.values() if isinstance(cached, dict) else []):
            if isinstance(p, dict) and (p.get("name") or "").lower() == lname:
                product = p
                break

    # If not found, use resolver to hydrate product blob (cache-first)
    if product is None and product_id:
        try:
            blobs = await resolve_required_blobs(store=store, session_id=session_id, required_blobs=[f"product:{product_id}"], ice_client=ice_client, event_id=event_id)
            product = blobs.get(f"product:{product_id}")
        except Exception:
            product = None

    if product:
        reply_text = f"{product.get('name')} — Price: {product.get('price')} {product.get('currency','')}. {product.get('description','')}"
    else:
        if product_name:
            reply_text = f"I couldn't find details for '{product_name}'. Try searching or say 'browse categories'."
        else:
            reply_text = "Which product would you like details for? Say a product name or pick from categories."

    return {"oob": oob, "oob_ver": ver, "reply_text": reply_text, "product": product}
