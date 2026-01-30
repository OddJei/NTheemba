from __future__ import annotations

from typing import Any, Dict

from ..oob_store import OOBStore
from ..resolver import resolve_required_blobs


async def greet_and_suggest(
    *,
    store: OOBStore,
    session_id: str,
    event_id: str | None = None,
    ice_client=None,
) -> dict[str, Any]:
    """Ensure OOB exists and return a short greeting with lightweight suggestions.

    This handler is cache-first: it will not mutate OOB. If an `ice_client` is
    provided it will ask ICE for simple recommendations; otherwise returns a
    friendly greeting and a short list of example actions.
    """

    oob, ver = await store.create_default_if_missing(session_id)

    recommendations: list[Dict[str, Any]] = []
    if ice_client is not None:
        # Ask resolver for recommendations (cache-first). If ICE is present the
        # resolver will call ice_client.hydrate(...) for the requested blob.
        try:
            resp = await resolve_required_blobs(
                store=store, session_id=session_id, required_blobs=["recommendations"], ice_client=ice_client, event_id=event_id
            )
            recommendations = resp.get("recommendations") if isinstance(resp, dict) else []
        except Exception:
            recommendations = []

    if recommendations:
        names = ", ".join([str(it.get("title") or it.get("product_name") or it.get("id")) for it in recommendations[:3]])
        reply_text = f"Hi — I recommend: {names}. What would you like to do?"
    else:
        reply_text = "Hi — what would you like today? You can say things like '2 apples' or 'view cart'."

    return {"oob": oob, "oob_ver": ver, "reply_text": reply_text, "recommendations": recommendations}
