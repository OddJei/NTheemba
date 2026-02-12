from __future__ import annotations

from typing import Any, Dict, List

from ..oob_store import OOBStore
from ..resolver import resolve_required_blobs


async def greet_and_suggest(
    *,
    store: OOBStore,
    session_id: str,
    event_id: str | None = None,
    ice_client=None,
    raw_text: str | None = None,
) -> dict[str, Any]:
    """Greet the user with persona 'NTheemba', resolve business name and products via ICE,
    build a context snapshot and produce a reply with light Bemba/Nyanja mixed in.
    """

    PERSONA = "NTheemba"

    oob, ver = await store.create_default_if_missing(session_id)

    diagnostics: Dict[str, List[str] | str] = {"missing": [], "notes": []}

    # Resolve business metadata and products via resolver (cache-first)
    business_name = None
    suggested_products: List[Dict[str, Any]] = []

    # Try resolver hydrate for 'business' and 'products'
    if ice_client is not None:
        try:
            resp = await resolve_required_blobs(store=store, session_id=session_id, required_blobs=["business", "products"], ice_client=ice_client, event_id=event_id)
        except Exception:
            resp = {}

        # business blob may be a dict with 'name'
        business_blob = resp.get("business") if isinstance(resp, dict) else None
        if isinstance(business_blob, dict):
            business_name = business_blob.get("name")

        # products blob could be a list
        products_blob = resp.get("products") if isinstance(resp, dict) else None
        if isinstance(products_blob, list) and products_blob:
            # pick 2-3 products
            suggested_products = products_blob[:3]

        # If business missing after hydrate, attempt lookup by phone
        if not business_name:
            # try session meta or oob for business phone
            business_phone = None
            try:
                meta = oob.get("meta") or {}
                business_phone = meta.get("business_phone") or meta.get("business_number")
            except Exception:
                business_phone = None

            if business_phone and hasattr(ice_client, "get_business_by_phone"):
                try:
                    biz = await ice_client.get_business_by_phone(phone=str(business_phone), session_id=session_id)
                    if isinstance(biz, dict):
                        business_name = biz.get("name")
                        # write back into hydrated blobs via resolver pattern
                        def _upd(o: dict[str, Any]) -> dict[str, Any]:
                            o = dict(o)
                            m = dict(o.get("meta") or {})
                            hb = dict(m.get("hydrated_blobs") or {})
                            hb["business"] = biz
                            m["hydrated_blobs"] = hb
                            o["meta"] = m
                            return o

                        try:
                            await store.cas_update(session_id, _upd)
                        except Exception:
                            pass
                except Exception:
                    diagnostics.setdefault("missing", []).append("business_lookup_failed")
                    diagnostics.setdefault("notes", []).append("ICE business lookup by phone failed")

        # If still no business name, record unresolved
        if not business_name:
            diagnostics.setdefault("missing", []).append("business_name_unresolved")
            diagnostics.setdefault("notes", []).append("Business name not found in cache or ICE")

    else:
        diagnostics.setdefault("missing", []).append("ice_not_configured")
        diagnostics.setdefault("notes", []).append("ICE client not provided; recommendations unavailable")

    # If no suggested products yet, try ICE recommendations endpoint directly
    if ice_client is not None and not suggested_products:
        try:
            try:
                recs = await ice_client.get_recommendations(session_id=session_id, count=3)
            except TypeError:
                recs = await ice_client.get_recommendations(session_id)
            if isinstance(recs, dict):
                items = recs.get("items")
            elif isinstance(recs, list):
                items = recs
            else:
                items = None
            if isinstance(items, list) and items:
                suggested_products = items[:3]
            else:
                diagnostics.setdefault("missing", []).append("no_product_suggestions")
                diagnostics.setdefault("notes", []).append("No product suggestions in cache or ICE")
        except Exception:
            diagnostics.setdefault("missing", []).append("product_suggestion_failed")
            diagnostics.setdefault("notes", []).append("ICE recommendations call failed")

    # Build user_state snapshot
    user_state = {
        "stage": "chat",
        "business_name": business_name,
        "bot_persona": PERSONA,
        "suggested_products": [
            {"id": p.get("id"), "name": p.get("title") or p.get("name") or p.get("product_name"), "price": p.get("price")}
            for p in (suggested_products or [])[:3]
        ],
    }

    # Construct reply with light Bemba/Nyanja mixing
    biz_display = business_name or "your store"
    product_names = [p.get("name") for p in user_state.get("suggested_products") or [] if p.get("name")]
    if product_names:
        if len(product_names) == 1:
            prod_list = product_names[0]
        elif len(product_names) == 2:
            prod_list = f"{product_names[0]} and {product_names[1]}"
        else:
            prod_list = ", ".join(product_names[:-1]) + f", and {product_names[-1]}"
        reply_text = f"Hi! Muli bwanji! {PERSONA} here from {biz_display}. Nomba, we have {prod_list} today — would you like to add one to your cart?"
    else:
        reply_text = f"Hi! Muli bwanji! {PERSONA} here from {biz_display}. How can I help you today?"

    # Ensure diagnostics fields are string/list as expected
    notes_val = "; ".join(diagnostics.get("notes") or []) if isinstance(diagnostics.get("notes"), list) else diagnostics.get("notes")

    return {
        "oob": oob,
        "oob_ver": ver,
        "reply_text": reply_text,
        "recommendations": user_state.get("suggested_products"),
        "context_snapshot": {
            "user_state": user_state,
            "diagnostics": {"missing": diagnostics.get("missing") or [], "notes": notes_val},
            "user_text": raw_text,
        },
    }
