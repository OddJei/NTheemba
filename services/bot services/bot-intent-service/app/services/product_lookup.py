from __future__ import annotations

from typing import Any, Dict, List


async def lookup_products_from_request(request) -> List[Dict[str, Any]]:
    """Return a small product snapshot for the prompt.

    Strategy:
    - Prefer a compact `catalog_snapshot` supplied in `request.context` or `request.enriched_meta`.
    - Snapshot entries should be dicts with at least `product_id`, `name`, and optional `aliases`.
    - This function is intentionally simple: the runtime may replace it with a resolver-backed cache-first lookup.
    """
    ctx = getattr(request, "context", None) or {}
    snap = None
    if isinstance(ctx, dict):
        snap = ctx.get("catalog_snapshot")

    if not snap:
        meta = getattr(request, "enriched_meta", None) or {}
        if isinstance(meta, dict):
            snap = meta.get("catalog_snapshot")

    if not snap:
        return []

    # normalize simple list-of-dicts
    out: List[Dict[str, Any]] = []
    for entry in snap:
        try:
            pid = entry.get("product_id") or entry.get("id")
            name = entry.get("name") or entry.get("title")
            aliases = entry.get("aliases") or entry.get("synonyms") or []
            out.append({"product_id": pid, "name": name, "aliases": list(aliases)})
        except Exception:
            continue
    return out
