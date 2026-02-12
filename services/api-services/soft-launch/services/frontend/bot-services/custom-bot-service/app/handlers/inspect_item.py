from __future__ import annotations

from typing import Any

from ..oob_store import OOBStore


async def inspect_item(
    *,
    store: OOBStore,
    session_id: str,
    product_name: str | None = None,
    line_index: int | None = None,
) -> dict[str, Any]:
    """Return details for a single cart line.

    Lookup can be by `product_name` (case-insensitive) or by `line_index` (0-based).
    This handler is read-only and does not perform CAS updates.
    """

    oob, ver = await store.get_oob(session_id)
    cart = oob.get("cart") or {}
    items = list(cart.get("items") or [])

    result_item: dict[str, Any] | None = None
    idx: int | None = None

    if line_index is not None:
        if 0 <= int(line_index) < len(items):
            idx = int(line_index)
            result_item = items[idx]
    elif product_name:
        pname = product_name.strip().lower()
        for i, it in enumerate(items):
            if isinstance(it, dict) and (it.get("product_name") or "").lower() == pname:
                idx = i
                result_item = it
                break

    return {
        "oob": oob,
        "oob_ver": ver,
        "found": result_item is not None,
        "item": result_item or {},
        "index": idx,
    }
