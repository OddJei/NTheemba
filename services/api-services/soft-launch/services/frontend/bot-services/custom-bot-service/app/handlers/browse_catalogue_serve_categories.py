from __future__ import annotations

from typing import Any, Dict

from ..oob_store import OOBStore
from ..resolver import resolve_required_blobs


async def serve_categories(
    *,
    store: OOBStore,
    session_id: str,
    event_id: str | None = None,
    ice_client=None,
) -> dict[str, Any]:
    """Return available categories. Cache-first: read bot config from Redis OOB meta if present.

    If `ice_client` is provided, request categories from ICE as a fallback/hydrator.
    This handler does not mutate OOB.
    """

    oob, ver = await store.create_default_if_missing(session_id)

    # Try to read categories from bot config in OOB.meta.bot_top_categories if present
    meta = oob.get("meta") or {}
    categories = meta.get("bot_top_categories") or []

    if not categories and ice_client is not None:
        try:
            resp = await resolve_required_blobs(
                store=store, session_id=session_id, required_blobs=["categories"], ice_client=ice_client, event_id=event_id
            )
            if isinstance(resp, dict):
                categories = resp.get("categories") or []
        except Exception:
            categories = []

    if categories:
        names = ", ".join([str(c.get("name") if isinstance(c, dict) else str(c)) for c in categories[:5]])
        reply_text = f"I can show categories: {names}. Which one would you like to browse?"
    else:
        reply_text = "I don't have categories right now. Tell me what you'd like to search for, e.g. 'apples'."

    return {"oob": oob, "oob_ver": ver, "reply_text": reply_text, "categories": categories}
