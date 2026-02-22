from __future__ import annotations

import logging
import time
import traceback
import asyncio
import uuid
import os
from typing import Any
import re

try:
    from .intent_parser import Intent, parse_intents
    from .oob_store import OOBStore
    from .ice_client import IceClient
    from .telemetry import emit_event, incr_metric
    from .audit_client import emit_audit
    from .session_cycle import start_cycle, complete_cycle, get_cycle
    from .handlers.resolve_multi_intent import resolve_multi_intent
    from .resolver import resolve_required_blobs
    from .handlers.add_item import add_item
    from .handlers.cart_view import view_cart
    from .handlers.remove_item import remove_item
    from .handlers.clear_cart import clear_cart
    from .handlers.help import help_text
    from .handlers.cancel import cancel_flow
    from .handlers.fallback_unknown_intent import fallback_reply
    from .handlers.inspect_item import inspect_item
    from .handlers.order_confirm_cart import confirm_cart
    from .handlers.order_validate_items import validate_items
    from .handlers.order_check_stock import check_stock
    from .handlers.order_calculate_total import calculate_total
    from .handlers.order_review_order import review_order
    from .handlers.confirm_order_gate import confirm_order_gate
    from .handlers.confirm_payment_gate import confirm_payment_gate
    from .handlers.payment_verify_status import verify_payment_status
    from .handlers.initiate_refund import initiate_refund
    from .handlers.fulfillment_choose_method import choose_method
    from .handlers.greet_and_suggest import greet_and_suggest
    from .handlers.browse_catalogue_serve_categories import serve_categories
    from .handlers.browse_catalogue_select_category import select_category
    from .handlers.browse_catalogue_serve_products import serve_products
    from .handlers.browse_catalogue_select_product import select_product
    from .handlers.browse_catalogue_show_product_details import show_product_details
    from .handlers.fulfillment_select_delivery_option import select_delivery_option
    from .handlers.fulfillment_choose_location import choose_location
    from .handlers.affiliate_capture_code import capture_code
    from .handlers.affiliate_track_click import track_click
    from .nlg_renderer import render_reply
except Exception:
    from intent_parser import Intent, parse_intents
    from oob_store import OOBStore
    from ice_client import IceClient
    from telemetry import emit_event, incr_metric
    from audit_client import emit_audit
    from session_cycle import start_cycle, complete_cycle, get_cycle
    from handlers.resolve_multi_intent import resolve_multi_intent
    from resolver import resolve_required_blobs
    from handlers.add_item import add_item
    from handlers.cart_view import view_cart
    from handlers.remove_item import remove_item
    from handlers.clear_cart import clear_cart
    from handlers.help import help_text
    from handlers.cancel import cancel_flow
    from handlers.fallback_unknown_intent import fallback_reply
    from handlers.inspect_item import inspect_item
    from handlers.order_confirm_cart import confirm_cart
    from handlers.order_validate_items import validate_items
    from handlers.order_check_stock import check_stock
    from handlers.order_calculate_total import calculate_total
    from handlers.order_review_order import review_order
    from handlers.confirm_order_gate import confirm_order_gate
    from handlers.confirm_payment_gate import confirm_payment_gate
    from handlers.payment_verify_status import verify_payment_status
    from handlers.initiate_refund import initiate_refund
    from handlers.fulfillment_choose_method import choose_method
    from handlers.greet_and_suggest import greet_and_suggest
    from handlers.browse_catalogue_serve_categories import serve_categories
    from handlers.browse_catalogue_select_category import select_category
    from handlers.browse_catalogue_serve_products import serve_products
    from handlers.browse_catalogue_select_product import select_product
    from handlers.browse_catalogue_show_product_details import show_product_details
    from handlers.fulfillment_select_delivery_option import select_delivery_option
    from handlers.fulfillment_choose_location import choose_location
    from handlers.affiliate_capture_code import capture_code
    from handlers.affiliate_track_click import track_click
    from nlg_renderer import render_reply

logger = logging.getLogger("custom_bot.engine")


async def ensure_session_and_cycle(*, payload: dict[str, Any], session_id: str | None, bot_meta: dict[str, Any], business_meta: dict[str, Any], event_id: str | None, ice_client: IceClient) -> tuple[str | None, str | None, str]:
    """Ensure session exists via ICE (authoritative). Returns (session_id, cycle_id, current_stage).

    If session_id provided, attempt to fetch current stage via ICE hydrate; otherwise ask ICE to create session.
    """
    # Extract phone and platform from payload/meta
    phone = None
    try:
        phone = payload.get("from") or payload.get("buyer_phone") or (payload.get("meta") or {}).get("phone")
    except Exception:
        phone = None

    platform = (payload.get("platform") or (payload.get("meta") or {}).get("platform") or "whatsapp").lower()
    bot_id = bot_meta.get("bot_id") or bot_meta.get("id")

    if session_id and ice_client and ice_client.enabled:
        # best-effort hydrate to discover current stage/cycle via ICE
        try:
            resp = await ice_client.hydrate(session_id=session_id, required_blobs=["session_meta"], event_id=event_id)
            session_meta = resp.get("session_meta") or {}
            current_stage = session_meta.get("current_stage") or "chat"
            cycle_id = session_meta.get("current_cycle_id")
            
            # Check for cycle resolution metadata
            cycle_resolution = session_meta.get("cycle_resolution") or {}
            if cycle_resolution.get("should_start_new_chat_cycle"):
                # Last cycle was completed, start a new chat cycle
                try:
                    new_cycle = await start_cycle(session_id, "chat", meta={"previous_context": cycle_resolution.get("last_cycle_context")})
                    cycle_id = f"{session_id}:chat"  # Use the Redis key format as cycle_id
                    logger.info(f"Started new chat cycle for session {session_id} with previous context")
                    # Best-effort: inform ICE/bot-session to persist cycle meta server-side
                    try:
                        if ice_client and getattr(ice_client, 'enabled', False):
                            await ice_client.update_stage(session_id=session_id, cycle_id=None, new_stage="chat", context={"previous_context": cycle_resolution.get("last_cycle_context")}, event_id=event_id)
                    except Exception:
                        # non-fatal: proceed even if server-side persistence fails
                        pass
                except Exception as e:
                    logger.warning(f"Failed to start new chat cycle: {e}")
            
            return session_id, cycle_id, current_stage
        except Exception:
            return session_id, None, "chat"

    # No session_id: ask ICE to create/resolve a session
    if not ice_client or not ice_client.enabled:
        return None, None, "chat"

    try:
        resp = await ice_client.create_session(user_phone=phone or "", bot_id=bot_id, platform=platform, business_id=business_meta.get("id"), event_id=event_id)
        # ICE expected to return session_id and optionally cycle_id/current_stage
        sid = resp.get("session_id")
        cid = resp.get("cycle_id") or resp.get("current_cycle_id")
        stage = resp.get("current_stage") or resp.get("stage") or "chat"
        return sid, cid, stage
    except Exception:
        return None, None, "chat"


async def upgrade_stage_if_chat(*, store: "OOBStore", session_id: str, cycle_id: str | None, current_stage: str, snapshot: dict[str, Any], event_id: str | None, ice_client: IceClient) -> tuple[str | None, dict[str, Any]]:
    """If current_stage == 'chat', request ICE to upgrade to 'cart' with provided snapshot.

    Returns (new_cycle_id, ice_resp_blobs)
    """
    if current_stage != "chat":
        return None, {}
    try:
        resp = await ice_client.update_stage(session_id=session_id, cycle_id=cycle_id, new_stage="cart", context=snapshot, event_id=event_id)
    except Exception:
        return None, {}

    # ICE may return hydrated blobs to merge into OOB
    blobs = resp.get("hydrated_blobs") or {}
    if blobs:
        try:
            async def _upd(o: dict[str, Any]) -> dict[str, Any]:
                o = dict(o)
                m = dict(o.get("meta") or {})
                hb = dict(m.get("hydrated_blobs") or {})
                hb.update(blobs)
                m["hydrated_blobs"] = hb
                o["meta"] = m
                o["last_node_executed"] = "ice.update_stage"
                return o

            await store.cas_update(session_id, _upd)
        except Exception:
            pass

    # Do not create a new cycle when upgrading; prefer existing cycle_id when provided.
    new_cycle_id = cycle_id if cycle_id else (resp.get("cycle_id") or resp.get("new_cycle_id"))
    return new_cycle_id, blobs


async def execute_multi_intent_mapper(*, store: "OOBStore", session_id: str, mapper: dict[str, Any], event_id: str | None, ice_client: IceClient) -> list[dict[str, Any]]:
    """Execute intents described in mapper sequentially and return per-intent results.

    Mapper format: {"intents": [{"id": "add_item", "slots": {...}}, ...]}
    """
    results: list[dict[str, Any]] = []
    intents = mapper.get("intents") if isinstance(mapper, dict) else None
    if not isinstance(intents, list):
        return results

    for it in intents:
        if not isinstance(it, dict):
            continue
        intent_id = it.get("id") or it.get("intent")
        slots = it.get("slots") or {}
        res = {"intent_id": intent_id, "status": "skipped"}
        try:
            if intent_id == "add_item":
                product_name = str(slots.get("product_name") or "").strip()
                quantity = int(slots.get("quantity") or 1)
                await add_item(store=store, session_id=session_id, event_id=event_id, product_name=product_name, quantity=quantity)
                res["status"] = "ok"
            elif intent_id == "view_cart":
                summary = await view_cart(store=store, session_id=session_id)
                res["status"] = "ok"
                res["summary"] = summary
            elif intent_id == "inspect_item":
                await inspect_item(store=store, session_id=session_id, event_id=event_id)
                res["status"] = "ok"
            else:
                # fallback: no-op but mark as unknown
                res["status"] = "unknown_intent"
        except Exception:
            res["status"] = "error"
        results.append(res)

    return results


def build_final_context(*, snapshot: dict[str, Any], mapper_results: list[dict[str, Any]], store_oob: dict[str, Any]) -> dict[str, Any]:
    """Build final context payload to send to Gemini / NLG using snapshot and mapper results.

    Aligns with bot-session `_build_cycle_context` expectations (provides `user_text`, optional `cart_items`).
    """
    ctx: dict[str, Any] = {}
    user_text = (snapshot.get("user_text") or "")
    ctx["user_text"] = user_text
    # cart items from OOB if present
    try:
        cart_items = (store_oob.get("cart") or {}).get("items") if isinstance(store_oob, dict) else []
    except Exception:
        cart_items = []
    if cart_items:
        ctx["cart_items"] = cart_items
        ctx["checkout"] = True

    # include diagnostics and mapper details
    ctx["diagnostics"] = snapshot.get("diagnostics") or {}
    ctx["intent_mapper_results"] = mapper_results or []
    # include raw snapshot user_state for NLG
    ctx["user_state"] = snapshot.get("user_state") or {}
    return ctx


if __name__ == "__main__":
    # Simple demo simulation for browse flow using a FakeIce that returns >5 products
    import asyncio

    class FakeIce:
        def __init__(self):
            self.enabled = True

        async def hydrate(self, *, session_id: str, required_blobs: list[str], event_id: str | None = None):
            # build sample categories
            categories = [{"id": "c1", "name": "Bakery"}, {"id": "c2", "name": "Dairy"}]
            # sample products >5
            products = [
                {"id": f"p{i}", "name": f"Bread {i}", "price": 50 + i, "category_id": "c1" if i % 2 == 0 else "c2"}
                for i in range(1, 8)
            ]
            key = None
            for k in required_blobs:
                if k.startswith("products"):
                    key = k
                    break
            resp = {}
            if key:
                resp[key] = products
            resp["products"] = products
            resp["categories"] = categories
            resp["category_slots"] = {"c1": ["slot1"], "c2": ["slot2"]}
            return resp

    async def _demo():
        fake_ice = FakeIce()
        store = OOBStore()
        grouped, cats, slots, diag = await fetch_and_group_products(store=store, session_id="demo-session", category_id=None, ice_client=fake_ice, event_id="demo")
        ctx = build_catalogue_context(snapshot={"user_text": "I want bread", "user_state": {}, "diagnostics": {}}, grouped_products=grouped, categories=cats, slots=slots, store_oob={})
        print("GROUPED:")
        print(grouped)
        print("CATEGORIES:")
        print(cats)
        print("SLOTS:")
        print(slots)
        print("CONTEXT:")
        print(ctx)

    asyncio.run(_demo())


async def resolve_stage_via_ice(*, payload: dict[str, Any], session_id: str | None, bot_meta: dict[str, Any], business_meta: dict[str, Any], event_id: str | None, ice_client: IceClient) -> tuple[str | None, str | None, str]:
    """Resolve or create an authoritative session and return (session_id, cycle_id, current_stage).

    Uses the existing `ensure_session_and_cycle` helper but exposes a clearer name for catalogue flows.
    """
    try:
        sid, cid, stage = await ensure_session_and_cycle(payload=payload, session_id=session_id, bot_meta=bot_meta, business_meta=business_meta, event_id=event_id, ice_client=ice_client)
        return sid, cid, stage
    except Exception:
        return session_id, None, "chat"


async def fetch_and_group_products(*, store: OOBStore, session_id: str | None, category_id: str | None, ice_client: IceClient | None, event_id: str | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """Fetch products and categories via ICE hydrate and return grouped products, categories list, slots map, diagnostics.

    Grouping rule: when product count > 5, group by `category_id`. Each product entry keeps only `id`, `name`, `price`.
    """
    diagnostics: dict[str, Any] = {"notes": []}
    if not ice_client or not ice_client.enabled:
        return [], [], {}, diagnostics

    # Determine required blob keys
    key = f"products:category:{category_id}" if category_id else "products"
    req = [key, "categories", "category_slots"]
    try:
        resp = await ice_client.hydrate(session_id=session_id or "", required_blobs=req, event_id=event_id)
    except Exception:
        resp = {}

    # Extract blobs
    products = resp.get(key) or resp.get("products") or []
    categories_blob = resp.get("categories") or []
    slots = resp.get("category_slots") or {}

    # Normalize categories to list of {id,name}
    categories_map: dict[str, str] = {}
    cats_out: list[dict[str, Any]] = []
    if isinstance(categories_blob, list):
        for c in categories_blob:
            try:
                cid = str(c.get("id"))
                cname = c.get("name") or c.get("title") or ""
                categories_map[cid] = cname
                cats_out.append({"id": cid, "name": cname})
            except Exception:
                continue

    # Ensure products is a list
    if not isinstance(products, list):
        diagnostics.setdefault("notes", []).append("products_blob_not_list")
        products = []

    # Grouping
    grouped: dict[str, list[dict[str, Any]]] = {}
    if len(products) > 5:
        for p in products:
            try:
                pid = str(p.get("id") or p.get("product_id"))
                name = p.get("name") or p.get("title") or ""
                price = p.get("price") if (p.get("price") is not None) else p.get("selling_price")
                catid = str(p.get("category_id") or p.get("category") or "")
                entry = {"id": pid, "name": name, "price": price}
                grouped.setdefault(catid or "", []).append(entry)
            except Exception:
                continue
    else:
        # Single group (flat list)
        grp: list[dict[str, Any]] = []
        for p in products:
            try:
                pid = str(p.get("id") or p.get("product_id"))
                name = p.get("name") or p.get("title") or ""
                price = p.get("price") if (p.get("price") is not None) else p.get("selling_price")
                grp.append({"id": pid, "name": name, "price": price})
            except Exception:
                continue
        grouped[category_id or ""] = grp

    # Convert grouped dict to list of groups with category metadata
    grouped_out: list[dict[str, Any]] = []
    for cid, items in grouped.items():
        grouped_out.append({"category_id": cid, "category_name": categories_map.get(cid) or "", "products": items})

    # Align slots to included categories
    aligned_slots: dict[str, Any] = {}
    if isinstance(slots, dict):
        for k, v in slots.items():
            if k in [g.get("category_id") for g in grouped_out]:
                aligned_slots[k] = v

    return grouped_out, cats_out, aligned_slots, diagnostics


def _local_bemba_mix(text: str) -> str:
    phrases = ["Muli bwanji!", "Nshakubwela.", "Nomba, shani?", "Zikomo!"]
    # append a short phrase to achieve light mixing
    return text + " " + phrases[0]


def build_catalogue_context(*, snapshot: dict[str, Any], grouped_products: list[dict[str, Any]], categories: list[dict[str, Any]], slots: dict[str, Any], store_oob: dict[str, Any]) -> dict[str, Any]:
    """Construct simplified catalogue context for Gemini.

    Includes: user_state, diagnostics, grouped_products (name,id,price), categories, slots.
    """
    ctx: dict[str, Any] = {}
    # user state
    ctx["user_text"] = (snapshot.get("user_text") or "")
    ctx["diagnostics"] = snapshot.get("diagnostics") or {}
    ctx["user_state"] = snapshot.get("user_state") or {}

    # categories and groups
    ctx["categories"] = categories or []
    ctx["groups"] = grouped_products or []

    # slots aligned with groups
    ctx["category_slots"] = slots or {}

    # include minimal cart info if present
    try:
        cart_items = (store_oob.get("cart") or {}).get("items") if isinstance(store_oob, dict) else []
    except Exception:
        cart_items = []
    if cart_items:
        ctx["cart_items"] = cart_items

    return ctx


async def enforce_cart_stage(*, payload: dict[str, Any], session_id: str | None, bot_meta: dict[str, Any], business_meta: dict[str, Any], event_id: str | None, store: OOBStore, ice_client: IceClient) -> tuple[str | None, str | None, str]:
    """Ensure session is at least in `cart` stage. If currently `chat`, run greet and upgrade via ICE to `cart`.

    Returns (session_id, cycle_id, current_stage)
    """
    # Resolve current stage
    sid, cid, stage = await resolve_stage_via_ice(payload=payload, session_id=session_id, bot_meta=bot_meta, business_meta=business_meta, event_id=event_id, ice_client=ice_client)
    if sid:
        session_id = sid

    if stage == "chat":
        # run greet to populate snapshot and possibly mapper intents
        try:
            resg = await greet_and_suggest(store=store, session_id=session_id, event_id=event_id, ice_client=ice_client, raw_text=_extract_raw_text(payload))
            snapshot = resg.get("context_snapshot") if isinstance(resg, dict) else {"user_state": {}, "diagnostics": {}, "user_text": _extract_raw_text(payload)}
        except Exception:
            snapshot = {"user_state": {}, "diagnostics": {}, "user_text": _extract_raw_text(payload)}

        # Ask ICE to upgrade stage from chat->cart using existing helper
        try:
            new_cycle_id, _ = await upgrade_stage_if_chat(store=store, session_id=session_id, cycle_id=cid, current_stage=stage, snapshot=snapshot, event_id=event_id, ice_client=ice_client)
            if new_cycle_id:
                cid = new_cycle_id
                stage = "cart"
        except Exception:
            pass

    return session_id, cid, stage


async def execute_cart_intents(*, store: OOBStore, session_id: str, intents: list[Intent], event_id: str | None, ice_client: IceClient) -> list[dict[str, Any]]:
    """Execute cart-related intents sequentially. Returns per-intent results."""
    results: list[dict[str, Any]] = []
    for it in intents:
        intent_id = it.id
        res = {"intent_id": intent_id, "status": "skipped"}
        try:
            if intent_id == "add_item":
                pname = str(it.slots.get("product_name") or it.slots.get("name") or "").strip()
                pid = str(it.slots.get("product_id") or it.slots.get("id") or "").strip()
                qty = int(it.slots.get("quantity") or 1)
                if not pname and pid:
                    pname = pid
                if pname and qty > 0:
                    await add_item(store=store, session_id=session_id, event_id=event_id, product_name=pname, quantity=qty)
                    res["status"] = "ok"
            elif intent_id == "remove_item":
                pname = str(it.slots.get("product_name") or it.slots.get("name") or "").strip()
                if pname:
                    await remove_item(store=store, session_id=session_id, product_name=pname, event_id=event_id)
                    res["status"] = "ok"
            elif intent_id == "view_cart":
                summary = await view_cart(store=store, session_id=session_id)
                res["status"] = "ok"
                res["summary"] = summary
            elif intent_id == "clear_cart":
                await clear_cart(store=store, session_id=session_id, event_id=event_id)
                res["status"] = "ok"
            elif intent_id == "inspect_item":
                await inspect_item(store=store, session_id=session_id, event_id=event_id)
                res["status"] = "ok"
            elif intent_id == "browse_catalogue":
                # reuse fetch_and_group_products for catalogue listing
                await fetch_and_group_products(store=store, session_id=session_id, category_id=it.slots.get("category_id") or None, ice_client=ice_client, event_id=event_id)
                res["status"] = "ok"
            elif intent_id == "confirm_cart":
                # validate cart, then initiate order stage
                try:
                    await confirm_cart(store=store, session_id=session_id, event_id=event_id)
                except Exception:
                    pass
                new_cid, _blobs = await confirm_cart_and_initiate_order(store=store, session_id=session_id, cycle_id=None, current_stage="cart", event_id=event_id, ice_client=ice_client)
                try:
                    review, _snapshot = await validate_and_review_order(store=store, session_id=session_id, event_id=event_id, ice_client=ice_client)
                except Exception:
                    review = {}
                res["status"] = "ok"
                res["new_cycle_id"] = new_cid
                res["order_review"] = review
            elif intent_id == "help":
                res["status"] = "ok"
                res["reply"] = help_text()
            elif intent_id == "cancel":
                # best-effort cancel: clear cart and mark session inactive
                await clear_cart(store=store, session_id=session_id, event_id=event_id)
                res["status"] = "ok"
            else:
                res["status"] = "unknown"
        except Exception:
            res["status"] = "error"
        results.append(res)
    return results


def build_cart_context(*, snapshot: dict[str, Any], store_oob: dict[str, Any], mapper_results: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Build snapshot for cart stage aligned with bot-session expectations.

    Includes user_state, diagnostics, cart_items (id,name,price), checkout flag when present, and mapper results.
    """
    ctx: dict[str, Any] = {}
    ctx["user_text"] = (snapshot.get("user_text") or "")
    ctx["diagnostics"] = snapshot.get("diagnostics") or {}
    ctx["user_state"] = snapshot.get("user_state") or {}

    try:
        cart_items = (store_oob.get("cart") or {}).get("items") if isinstance(store_oob, dict) else []
    except Exception:
        cart_items = []

    # Normalize items to only id,name,price
    normalized = []
    if isinstance(cart_items, list):
        for it in cart_items:
            try:
                normalized.append({"id": str(it.get("product_id") or it.get("id") or it.get("product_name") or ""), "name": it.get("product_name") or it.get("name") or "", "price": it.get("price")})
            except Exception:
                continue

    ctx["cart_items"] = normalized
    ctx["checkout"] = bool(normalized)
    ctx["intent_mapper_results"] = mapper_results or []
    return ctx


def build_payment_context(
    *,
    snapshot: dict[str, Any],
    store_oob: dict[str, Any],
    order_id: str | None,
    payment_phone: str | None,
    delivery_option: str | None,
    delivery_town: str | None,
    delivery_address: str | None,
    total_price: Any,
) -> dict[str, Any]:
    """Build payment/delivery snapshot aligned with bot-session expectations."""
    ctx: dict[str, Any] = {}
    ctx["user_text"] = (snapshot.get("user_text") or "")
    ctx["diagnostics"] = snapshot.get("diagnostics") or {}
    ctx["user_state"] = snapshot.get("user_state") or {}

    cart_items = (store_oob.get("cart") or {}).get("items") if isinstance(store_oob, dict) else []
    normalized: list[dict[str, Any]] = []
    if isinstance(cart_items, list):
        for it in cart_items:
            try:
                normalized.append({
                    "id": str(it.get("product_id") or it.get("id") or it.get("product_name") or ""),
                    "name": it.get("product_name") or it.get("name") or "",
                    "price": it.get("price"),
                })
            except Exception:
                continue

    ctx["order_id"] = order_id
    ctx["cart_items"] = normalized
    ctx["payment_phone"] = payment_phone
    ctx["delivery_option"] = delivery_option
    if delivery_town or delivery_address:
        ctx["delivery_location"] = {"town": delivery_town, "address": delivery_address}
    ctx["total_price"] = total_price
    ctx["payment_method"] = "mobile_money"
    return ctx


async def confirm_cart_and_initiate_order(
    *,
    store: OOBStore,
    session_id: str,
    cycle_id: str | None,
    current_stage: str,
    event_id: str | None,
    ice_client: IceClient,
    raw_text: str | None = None,
    snapshot: dict[str, Any] | None = None,
) -> tuple[str | None, dict[str, Any]]:
    """Ask ICE to promote the session/cycle to `order` with cart snapshot. Returns (new_cycle_id, hydrated_blobs).

    Also merges any returned hydrated_blobs into OOB via cas_update.
    """
    if not ice_client or not ice_client.enabled:
        return None, {}

    try:
        oob, _ = await store.create_default_if_missing(session_id)
    except Exception:
        oob = {}

    base_snapshot = snapshot or {"user_text": raw_text or "confirming cart", "diagnostics": {}, "user_state": {}}
    snapshot_ctx = build_cart_context(snapshot=base_snapshot, store_oob=oob, mapper_results=None)

    try:
        resp = await ice_client.update_stage(session_id=session_id, cycle_id=cycle_id, new_stage="order", context=snapshot_ctx, event_id=event_id)
    except Exception:
        return None, {}

    blobs = resp.get("hydrated_blobs") or {}
    if blobs:
        try:
            async def _upd(o: dict[str, Any]) -> dict[str, Any]:
                o = dict(o)
                m = dict(o.get("meta") or {})
                hb = dict(m.get("hydrated_blobs") or {})
                hb.update(blobs)
                m["hydrated_blobs"] = hb
                m["order_context"] = snapshot_ctx
                o["meta"] = m
                o["last_node_executed"] = "ice.update_stage.confirm_cart"
                return o

            await store.cas_update(session_id, _upd)
        except Exception:
            pass

    # Prefer updating existing cycle; do not create a new one if cycle_id provided.
    new_cid = cycle_id if cycle_id else (resp.get("cycle_id") or resp.get("new_cycle_id"))
    return new_cid, blobs


async def validate_and_review_order(*, store: OOBStore, session_id: str, event_id: str | None, ice_client: IceClient) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run validation, stock reservation, pricing and produce an order review summary and snapshot."""
    # local validation
    try:
        await validate_items(store=store, session_id=session_id, event_id=event_id)
    except Exception:
        pass

    # check stock (authoritative)
    try:
        await check_stock(store=store, session_id=session_id, event_id=event_id, ice_client=ice_client)
    except Exception:
        pass

    # calculate totals
    try:
        await calculate_total(store=store, session_id=session_id, event_id=event_id, ice_client=ice_client)
    except Exception:
        pass

    # review order (read-only summary)
    review = await review_order(store=store, session_id=session_id)

    # build snapshot aligning with bot-session expectations
    oob = review.get("oob") or {}
    cart_items = []
    for it in (review.get("items") or []):
        try:
            cart_items.append({"id": it.get("product_id") or it.get("id") or None, "name": it.get("product_name") or it.get("name") or "", "price": it.get("price")})
        except Exception:
            continue

    snapshot = {
        "user_state": {},
        "diagnostics": oob.get("meta") or {},
        "cart_items": cart_items,
        "order_summary": {"totals": review.get("totals"), "items_count": review.get("items_count")},
        "payment": {},
    }

    return review, snapshot


async def transition_to_payment(*, store: OOBStore, session_id: str, cycle_id: str | None, order_id: str, event_id: str | None, ice_client: IceClient) -> dict[str, Any]:
    """When user confirms order summary, transition stage to `payment` with order details and start payment cycle."""
    # fetch review to get totals
    review = await review_order(store=store, session_id=session_id)
    totals = review.get("totals") or {}

    cart_items = []
    for it in (review.get("items") or []):
        try:
            cart_items.append({"id": it.get("product_id") or it.get("id") or None, "name": it.get("product_name") or it.get("name") or "", "price": it.get("price")})
        except Exception:
            continue

    ctx = {
        "order_id": order_id,
        "cart_items": cart_items,
        "total_price": (totals.get("grand_total") if isinstance(totals, dict) else None),
        "payment_method": "mobile_money",
    }

    try:
        resp = await ice_client.update_stage(session_id=session_id, cycle_id=cycle_id, new_stage="payment", context=ctx, event_id=event_id)
    except Exception:
        resp = {}

    # start payment cycle in bot-session
    try:
        await start_cycle(session_id, "payment", meta={"order_id": order_id})
    except Exception:
        pass

    # persist order meta for downstream payment/delivery steps
    try:
        async def _upd(o: dict[str, Any]) -> dict[str, Any]:
            o = dict(o)
            meta = dict(o.get("meta") or {})
            meta["order_id"] = order_id
            meta["total_price"] = ctx.get("total_price")
            o["meta"] = meta
            o["last_node_executed"] = "transition.to.payment"
            return o

        await store.cas_update(session_id, _upd)
    except Exception:
        pass

    return resp


def order_help() -> dict[str, Any]:
    """Return guidance for order stage actions."""
    text = (
        "You can: review your order, confirm to pay, cancel the order, or modify the cart. "
        "Say 'review' to see items, 'confirm' to proceed to payment, 'cancel' to cancel."
    )
    # light local language mix
    text = _local_bemba_mix(text)
    return {"render_type": "direct_gemini", "persona": "NTheemba", "text": text}


async def order_cancel(*, store: OOBStore, session_id: str, cycle_id: str | None, reason: str | None, event_id: str | None, ice_client: IceClient) -> dict[str, Any]:
    """Cancel the current order: ask ICE to set stage to `cancelled` and mark session cycle complete."""
    # build simple snapshot
    try:
        oob, ver = await store.get_oob(session_id)
    except Exception:
        oob = {}

    cart_items = []
    for it in (oob.get("cart") or {}).get("items") or []:
        try:
            cart_items.append({"id": it.get("product_id") or it.get("id") or None, "name": it.get("product_name") or it.get("name") or "", "price": it.get("price")})
        except Exception:
            continue

    ctx = {"reason": reason or "user_cancelled", "cart_items": cart_items}
    try:
        resp = await ice_client.update_stage(session_id=session_id, cycle_id=cycle_id, new_stage="cancelled", context=ctx, event_id=event_id)
    except Exception:
        resp = {}

    try:
        await complete_cycle(session_id, "order", extra_meta={"cancel_reason": reason})
    except Exception:
        pass

    text = "Your order has been cancelled. If you need anything else, let me know."
    text = _local_bemba_mix(text)
    return {"render_type": "direct_gemini", "persona": "NTheemba", "text": text, "ice_resp": resp}


def _validate_phone(phone: str) -> bool:
    try:
        if not isinstance(phone, str):
            return False
        p = phone.strip()
        # must start with country code 260
        return p.startswith("260") and len(p) >= 10
    except Exception:
        return False


def _validate_delivery_option(option: str) -> bool:
    if not isinstance(option, str):
        return False
    return option.lower() in ("pickup", "delivery")


async def fetch_business_delivery_locations(
    *,
    ice_client: IceClient,
    session_id: str | None = None,
    business_id: str | None = None,
    business_phone: str | None = None,
    business_meta: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Fetch available delivery towns and prices for the business.

    Uses ICE hydrate to request `delivery_locations` blob or business-specific key.
    """
    def _normalize(delivery_locations: Any) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if isinstance(delivery_locations, dict):
            for town, meta in delivery_locations.items():
                if not town:
                    continue
                entry = {"town_name": town}
                if isinstance(meta, dict):
                    price = meta.get("price_minor") or meta.get("price") or meta.get("delivery_price")
                    if price is not None:
                        entry["delivery_price"] = price
                out.append(entry)
        elif isinstance(delivery_locations, list):
            for it in delivery_locations:
                if not isinstance(it, dict):
                    continue
                out.append({
                    "town_name": it.get("town_name") or it.get("town") or it.get("name"),
                    "delivery_price": it.get("delivery_price") or it.get("price") or it.get("price_minor"),
                })
        return [row for row in out if row.get("town_name")]

    if business_meta and isinstance(business_meta, dict):
        meta_locs = business_meta.get("delivery_locations")
        if isinstance(meta_locs, (dict, list)):
            return _normalize(meta_locs)

    if not ice_client or not ice_client.enabled:
        return []

    if business_phone:
        try:
            resp = await ice_client.get_business_by_phone(phone=business_phone, session_id=session_id)
            business = resp.get("business") if isinstance(resp, dict) else None
            if isinstance(business, dict):
                locs = business.get("delivery_locations")
                if isinstance(locs, (dict, list)):
                    return _normalize(locs)
        except Exception:
            pass

    keys: list[str] = []
    if business_id:
        keys.append(f"business:{business_id}")
    keys.append("business")
    try:
        resp = await ice_client.hydrate(session_id=session_id or "", required_blobs=keys)
    except Exception:
        return []

    for key in keys:
        blob = resp.get(key)
        if isinstance(blob, dict) and isinstance(blob.get("delivery_locations"), (dict, list)):
            return _normalize(blob.get("delivery_locations"))
        # Some ICE implementations may return the list directly under the key
        if isinstance(blob, list):
            return _normalize(blob)
    return []


def validate_payment_inputs(
    *,
    phone: str | None,
    delivery_option: str | None,
    town: str | None,
    address: str | None = None,
    available_towns: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate payment inputs and return dict of errors (empty if valid)."""
    errors: dict[str, str] = {}
    if phone is None or not _validate_phone(str(phone)):
        errors["phone"] = "invalid_phone"
    if delivery_option is None or not _validate_delivery_option(str(delivery_option)):
        errors["delivery_option"] = "invalid_option"
    if delivery_option and delivery_option.lower() == "delivery":
        towns = [str(t.get("town_name")).lower() for t in (available_towns or []) if isinstance(t, dict) and t.get("town_name")]
        if not town or str(town).lower() not in towns:
            errors["town"] = "invalid_town"
        # Address is optional when a known town is provided; only validate if address present
        if address is not None and not str(address).strip():
            errors["address"] = "invalid_address"
    return errors


async def collect_payment_inputs_one_turn(*, payload: dict[str, Any], available_towns: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Extract payment inputs from payload in one turn. Returns inputs dict."""
    text = _extract_raw_text(payload) or ""
    # naive extraction: look for phone-like tokens and keywords
    parts = text.split()
    phone = None
    delivery_option = None
    town = None
    address = None
    for tok in parts:
        t = tok.strip().strip('.,')
        if t.startswith("260") and len(t) >= 10:
            phone = t
        if t.lower() in ("pickup", "delivery"):
            delivery_option = t.lower()
    # attempt to detect town from available towns
    if available_towns:
        town_names = [t.get("town_name") for t in available_towns if isinstance(t, dict)]
        for name in town_names:
            if name and name.lower() in text.lower():
                town = name
                break
    # remaining text as address
    address = text
    # Return both legacy keys (used by runtime) and normalized keys (used by tests)
    return {
        "payment_phone": phone,
        "delivery_option": delivery_option,
        "delivery_town": town,
        "delivery_address": address,
        "phone": phone,
        "town": town,
        "address": address,
        "raw_text": text,
    }


async def transition_to_delivery(
    *,
    store: OOBStore,
    session_id: str,
    cycle_id: str | None,
    order_id: str,
    payment_phone: str,
    delivery_option: str,
    delivery_town: str,
    delivery_address: str | None,
    event_id: str | None,
    ice_client: IceClient,
) -> dict[str, Any]:
    """After collecting and validating inputs, transition to `delivery` stage via ICE and start delivery cycle."""
    # build context
    try:
        oob, _ = await store.get_oob(session_id)
    except Exception:
        oob = {}

    cart_items = []
    for it in (oob.get("cart") or {}).get("items") or []:
        try:
            cart_items.append({"id": it.get("product_id") or it.get("id") or None, "name": it.get("product_name") or it.get("name") or "", "price": it.get("price")})
        except Exception:
            continue

    # totals if present
    totals = (oob.get("cart") or {}).get("totals") or {}

    snapshot = {
        "user_text": "confirming payment",
        "diagnostics": {},
        "user_state": {"stage": "delivery"},
    }
    ctx = build_payment_context(
        snapshot=snapshot,
        store_oob=oob,
        order_id=order_id,
        payment_phone=payment_phone,
        delivery_option=delivery_option,
        delivery_town=delivery_town,
        delivery_address=delivery_address,
        total_price=(totals.get("grand_total") if isinstance(totals, dict) else None),
    )

    try:
        resp = await ice_client.update_stage(session_id=session_id, cycle_id=cycle_id, new_stage="delivery", context=ctx, event_id=event_id)
    except Exception:
        resp = {}

    try:
        await start_cycle(session_id, "delivery", meta={"order_id": order_id, "delivery_town": delivery_town})
    except Exception:
        pass

    # instruct user for mobile money PIN entry
    text = f"Order {order_id} is almost set. Enter your PIN on {payment_phone} when prompted to complete payment."
    text = _local_bemba_mix(text)
    reply = {"render_type": "direct_gemini", "persona": "NTheemba", "text": text, "ice_resp": resp}

    # persist meta about payment
    try:
        async def _upd(o: dict[str, Any]) -> dict[str, Any]:
            o = dict(o)
            meta = dict(o.get("meta") or {})
            meta["payment_phone"] = payment_phone
            meta["delivery_option"] = delivery_option
            meta["delivery_location"] = {"town": delivery_town, "address": delivery_address}
            o["meta"] = meta
            o["last_node_executed"] = "transition.to.delivery"
            return o

        await store.cas_update(session_id, _upd)
    except Exception:
        pass

    return reply


def _extract_raw_text(payload: dict[str, Any]) -> str:
    # Common places where text lives.
    for path in (
        ("raw_text",),
        ("text",),
        ("message", "text"),
        ("payload", "text"),
        ("data", "text"),
        ("data", "message"),
    ):
        cur: Any = payload
        ok = True
        for key in path:
            if not isinstance(cur, dict) or key not in cur:
                ok = False
                break
            cur = cur[key]
        if ok and isinstance(cur, str) and cur.strip():
            return cur
    return ""


def _extract_meta(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        meta = payload.get("meta") if isinstance(payload, dict) else None
        return meta if isinstance(meta, dict) else {}
    except Exception:
        return {}


def _extract_session(payload: dict[str, Any]) -> dict[str, Any]:
    meta = _extract_meta(payload)
    session = meta.get("session") if isinstance(meta, dict) else None
    return session if isinstance(session, dict) else {}


def _extract_business(payload: dict[str, Any]) -> dict[str, Any]:
    meta = _extract_meta(payload)
    business = meta.get("business") if isinstance(meta, dict) else None
    return business if isinstance(business, dict) else {}


def _extract_bot(payload: dict[str, Any]) -> dict[str, Any]:
    meta = _extract_meta(payload)
    bot = meta.get("bot") if isinstance(meta, dict) else None
    return bot if isinstance(bot, dict) else {}


def _extract_stage(payload: dict[str, Any], session_meta: dict[str, Any]) -> str:
    try:
        meta = _extract_meta(payload)
        if isinstance(meta.get("stage"), str) and meta.get("stage").strip():
            return meta.get("stage").strip().lower()
    except Exception:
        pass

    stage = session_meta.get("stage") or session_meta.get("state")
    if isinstance(stage, str) and stage.strip():
        return stage.strip().lower()

    if isinstance(payload.get("stage"), str):
        return str(payload.get("stage")).strip().lower()

    return "chat"


def _canonical_ids_for_stage(stage: str) -> list[str]:
    if stage == "chat":
        return [
            "greet_and_suggest",
            "help",
            "cancel",
        ]
    if stage == "cart":
        return [
            "browse_catalogue",
            "add_item",
            "remove_item",
            "view_cart",
            "clear_cart",
            "inspect_item",
            "help",
            "cancel",
        ]
    if stage == "order":
        return [
            "order.confirm_cart",
            "order.review_order",
            "order.calculate_total",
            "order.check_stock",
            "confirm_order",
            "help",
            "cancel",
        ]
    if stage == "payment":
        return [
            "confirm_payment",
            "payment.verify_status",
            "help",
            "cancel",
        ]
    if stage == "delivery":
        return [
            "fulfillment.choose_method",
            "fulfillment.choose_location",
            "fulfillment.select_delivery_option",
            "refund.request",
            "refund.collect_reason",
            "help",
            "cancel",
        ]
    return [
        "help",
        "cancel",
    ]


STAGE_ORDER = ["chat", "cart", "order", "payment", "delivery", "closed"]

STAGE_REQUIRED_BLOBS: dict[str, list[str]] = {
    "chat": ["recommendations"],
    "cart": ["catalog", "products"],
    "order": ["pricing", "inventory"],
    "payment": ["payment_status"],
    "delivery": ["delivery_options"],
}

STAGE_AUTHORITATIVE_BLOBS: dict[str, list[str]] = {
    "order": ["pricing", "inventory"],
    "payment": ["payment_status"],
    "delivery": ["delivery_options"],
}

STAGE_REQUIRED_SLOTS: dict[str, list[str]] = {
    "cart": ["product_id"],
    "order": ["confirmation", "delivery_method"],
    "payment": [],
    "delivery": [],
}

SLOT_ALIASES: dict[str, list[str]] = {
    "product_id": ["product_id", "product", "id", "product_name", "name"],
    "confirmation": ["confirmation", "confirm", "confirmed", "yes_no"],
    "delivery_method": ["delivery_method", "method", "fulfillment_method"],
    "payment_number": ["payment_number", "mobile_number", "phone", "msisdn"],
    "fulfillment_method": ["fulfillment_method", "method", "delivery_method"],
    "location": ["location", "address", "pickup_location"],
}


def _intent_stage_lookup() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for st in STAGE_ORDER:
        for intent_id in _canonical_ids_for_stage(st):
            mapping.setdefault(intent_id, st)
    return mapping


INTENT_STAGE_MAP = _intent_stage_lookup()


def _intent_stage_for(intent: Intent, fallback_stage: str) -> str:
    if isinstance(intent.slots, dict):
        hint = intent.slots.get("__stage")
        if isinstance(hint, str) and hint in STAGE_ORDER:
            return hint
    return INTENT_STAGE_MAP.get(intent.id, fallback_stage)


def _stage_index(stage: str) -> int:
    try:
        return STAGE_ORDER.index(stage)
    except ValueError:
        return 0


def _build_stage_queue(current_stage: str, intents: list[Intent]) -> list[str]:
    if not intents:
        return [current_stage]

    current_idx = _stage_index(current_stage)
    min_idx = current_idx
    max_idx = current_idx
    for it in intents:
        st = _intent_stage_for(it, current_stage)
        idx = _stage_index(st)
        if idx < min_idx:
            min_idx = idx
        if idx > max_idx:
            max_idx = idx

    # If we're moving forward, include all prerequisites from current stage.
    if max_idx > current_idx:
        queue = STAGE_ORDER[current_idx : max_idx + 1]
    else:
        # Otherwise, allow going back without forcing forward stages.
        queue = STAGE_ORDER[min_idx : max_idx + 1]

    return queue if queue else [current_stage]


def _flatten_resolved_intents(resolved: dict[str, Any], current_stage: str) -> list[Intent]:
    intents_out: list[Intent] = []
    intents_raw = resolved.get("intents") if isinstance(resolved, dict) else None

    if isinstance(intents_raw, list):
        for it in intents_raw:
            if not isinstance(it, dict):
                continue
            intent_id = it.get("id") or it.get("intent_id")
            if not intent_id:
                continue
            slots = it.get("slots") if isinstance(it.get("slots"), dict) else {}
            intents_out.append(Intent(id=str(intent_id), slots=slots))
        return intents_out

    if isinstance(intents_raw, dict):
        for stage_name, stage_list in intents_raw.items():
            if not isinstance(stage_list, list):
                continue
            for it in stage_list:
                if not isinstance(it, dict):
                    continue
                intent_id = it.get("id") or it.get("intent_id")
                if not intent_id:
                    continue
                slots = it.get("slots") if isinstance(it.get("slots"), dict) else {}
                if stage_name in STAGE_ORDER:
                    # preserve explicit stage to enforce strict progression
                    slots = dict(slots)
                    slots["__stage"] = stage_name
                intents_out.append(Intent(id=str(intent_id), slots=slots))
        return intents_out

    return intents_out


def _collect_stage_slots(intents: list[Intent]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for it in intents:
        if not isinstance(it.slots, dict):
            continue
        for k, v in it.slots.items():
            if k not in merged and v not in (None, ""):
                merged[k] = v
    return merged


def _has_any_slot(slots: dict[str, Any], session_meta: dict[str, Any], aliases: list[str]) -> bool:
    for key in aliases:
        if key in slots and slots.get(key) not in (None, ""):
            return True
        if key in session_meta and session_meta.get(key) not in (None, ""):
            return True
    return False


def _missing_required_slots(stage: str, stage_intents: list[Intent], session_meta: dict[str, Any]) -> list[str]:
    required = STAGE_REQUIRED_SLOTS.get(stage) or []
    if not required:
        return []
    slots = _collect_stage_slots(stage_intents)
    missing: list[str] = []
    for req in required:
        aliases = SLOT_ALIASES.get(req, [req])
        if not _has_any_slot(slots, session_meta, aliases):
            missing.append(req)
    return missing


def _missing_slots_prompt(stage: str, missing: list[str]) -> str:
    if stage == "payment":
        return "Please share your mobile money number and account name."
    if stage == "delivery":
        return "Do you want delivery or pickup, and what's your location?"
    if stage == "order":
        return "Please confirm the order and your delivery method."
    if stage == "cart":
        return "Which products would you like? You can pick up to 3 items."
    if missing:
        return "Please provide: " + ", ".join(missing) + "."
    return "Please share the missing details to continue."


async def _force_hydrate_blobs(
    *,
    store: OOBStore,
    session_id: str,
    ice_client,
    blobs: list[str],
    event_id: str | None = None,
) -> dict[str, Any]:
    if not blobs or ice_client is None:
        return {}

    try:
        resp = await ice_client.hydrate(session_id=session_id, required_blobs=blobs, event_id=event_id)
    except Exception:
        resp = {}

    if not isinstance(resp, dict):
        return {}

    def _upd(o: dict[str, Any]) -> dict[str, Any]:
        o = dict(o)
        m = dict(o.get("meta") or {})
        hb = dict(m.get("hydrated_blobs") or {})
        nc = dict(m.get("negative_cache") or {})

        for k in blobs:
            v = resp.get(k)
            if v is None:
                nc[k] = int(time.time())
                hb.pop(k, None)
            else:
                hb[k] = v
                nc.pop(k, None)

        m["hydrated_blobs"] = hb
        m["negative_cache"] = nc
        o["meta"] = m
        o["last_node_executed"] = "resolver.hydrate.force"
        return o

    try:
        await store.cas_update(session_id, _upd)
    except Exception:
        pass

    return resp


async def _hydrate_stage_context(
    *,
    store: OOBStore,
    session_id: str,
    stage: str,
    ice_client,
    event_id: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {}

    cache_first = STAGE_REQUIRED_BLOBS.get(stage) or []
    authoritative = STAGE_AUTHORITATIVE_BLOBS.get(stage) or []

    if cache_first:
        try:
            cached = await resolve_required_blobs(
                store=store,
                session_id=session_id,
                required_blobs=cache_first,
                ice_client=ice_client,
                event_id=event_id,
            )
            if isinstance(cached, dict):
                result.update(cached)
        except Exception:
            pass

    if authoritative:
        try:
            refreshed = await _force_hydrate_blobs(
                store=store,
                session_id=session_id,
                ice_client=ice_client,
                blobs=authoritative,
                event_id=event_id,
            )
            if isinstance(refreshed, dict):
                result.update(refreshed)
        except Exception:
            pass

    return result


async def process_event(
    *,
    payload: dict[str, Any],
    event_id: str | None,
    session_id: str | None,
) -> dict[str, Any]:
    """Apply parsed intents to OOB and return a reply plan.

    Returns a dict with:
    - intent_ids
    - next_node
    - reply_text
    - oob_ref
    - oob_summary
    """
    raw_text = _extract_raw_text(payload)
    session_meta = _extract_session(payload)
    business_meta = _extract_business(payload)
    bot_meta = _extract_bot(payload)
    intents: list[Intent] = []

    # generate a trace id and root span for this top-level processing call for cross-event correlation
    trace_id = str(uuid.uuid4())
    root_span_id = str(uuid.uuid4())

    def _with_trace(d: dict[str, Any]) -> dict[str, Any]:
        try:
            d["trace_id"] = trace_id
            d["root_span_id"] = root_span_id
        except Exception:
            pass
        return d

    # Pre-intent short-circuit: detect affiliate token or marker and resolve via ICE
    try:
        token_match = re.search(r"ace:([a-z0-9]+)", raw_text)
        marker_match = re.search(r"\[\[AFFLINK\]\]", raw_text)
    except Exception:
        token_match = None
        marker_match = None

    if token_match or marker_match:
        # prefer explicit token when present
        token_full = token_match.group(0) if token_match else None
        # best-effort buyer phone and session id extraction from payload
        buyer_phone = None
        try:
            buyer_phone = payload.get("from") or payload.get("buyer_phone") or (payload.get("meta") or {}).get("phone")
        except Exception:
            buyer_phone = None

        # ensure we have an ICE client
        ice = IceClient()
        if ice.enabled and token_full:
            try:
                prod = await ice.resolve_token(token=token_full, buyer_phone=buyer_phone, session_id=session_id, event_id=event_id)
                # prod expected to contain product details
                if prod and isinstance(prod, dict) and prod.get("id"):
                    # orchestrator: start a cart cycle for this session when token initiates a cart
                    try:
                        if session_id:
                            await start_cycle(session_id=session_id, cycle_type="cart", initiated_by_affiliate=True, affiliate_code=token_full, affiliate_id=prod.get("affiliate_id"), meta={"product_id": prod.get("id")})
                    except Exception:
                        # best-effort; do not fail the token resolution path
                        pass

                    # attempt to add to OOB cart if session_id present
                    store = OOBStore()
                    added_ver = None
                    added_oob = None
                    if session_id:
                        def _add(oob: dict[str, Any]) -> dict[str, Any]:
                            o = dict(oob)
                            cart = dict(o.get("cart") or {})
                            items = list(cart.get("items") or [])
                            item = {"product_id": str(prod.get("id")), "product_name": prod.get("name"), "quantity": 1}
                            if prod.get("price") is not None:
                                item["price"] = prod.get("price")
                            if prod.get("affiliate_id"):
                                item["affiliate_id"] = prod.get("affiliate_id")
                            if prod.get("campaign"):
                                item["campaign"] = prod.get("campaign")
                            items.append(item)
                            cart["items"] = items
                            cart["status"] = cart.get("status") or "building"
                            o["cart"] = cart
                            if event_id:
                                o["last_event_id"] = event_id
                            o["last_node_executed"] = "token.resolve_add_item"
                            return o

                        try:
                            added_oob, added_ver = await store.cas_update(session_id, _add)
                        except Exception:
                            added_oob = None

                    # schedule audit and telemetry (non-blocking)
                    try:
                        r = getattr(store, "_r", None) if 'store' in locals() else None
                        if r is not None:
                            asyncio.create_task(emit_event(r, "affiliate_token_resolved", {"token": token_full, "product_id": prod.get("id"), "session_id": session_id}))
                        asyncio.create_task(emit_audit(service="custom-bot-service", event_type="affiliate_token_resolved", payload={"token": token_full, "product": prod, "session_id": session_id}, metadata={"trace_id": trace_id}))
                    except Exception:
                        pass

                    # prepare reply
                    pname = prod.get("name") or "product"
                    items_count = 0
                    if added_oob:
                        items_count = len((added_oob.get("cart") or {}).get("items") or [])
                    reply_text = f"Added {pname} to your cart. Cart now has {items_count} item(s). Reply 'REVIEW ORDER' to continue or 'ADD MORE' to add more items."
                    return _with_trace({
                        "intent_ids": ["affiliate.token"],
                        "next_node": "order.review_order",
                        "reply_text": reply_text,
                        "oob_ref": f"oob:{session_id}" if session_id else None,
                        "oob_summary": {"items_count": items_count, "oob_version": added_ver},
                    })
            except Exception:
                logger.exception("token_resolution_failed", extra={"token": token_full, "session_id": session_id})

    # Multi-stage execution path (default enabled).
    multi_stage_enabled = os.getenv("CUSTOM_BOT_MULTI_STAGE_ENABLED", "True") == "True"
    if multi_stage_enabled and session_id:
        store = OOBStore()

        ice = IceClient()
        ice_client = ice if ice.enabled else None

        # Determine initial stage window to resolve intents against.
        current_stage = _extract_stage(payload, session_meta)
        start_idx = _stage_index(current_stage)
        max_stage_span = int(os.getenv("CUSTOM_BOT_MAX_STAGE_SPAN", "3"))
        stage_window = STAGE_ORDER[start_idx : min(len(STAGE_ORDER), start_idx + max_stage_span)]

        canonical_ids: list[str] = []
        for st in stage_window:
            canonical_ids.extend(_canonical_ids_for_stage(st))
        canonical_ids = [x for i, x in enumerate(canonical_ids) if x not in canonical_ids[:i]]

        # Build cached blobs context.
        cached_blobs: dict[str, Any] = {}
        try:
            oob, _ver = await store.create_default_if_missing(session_id)
            meta = oob.get("meta") or {}
            cached_blobs = meta.get("hydrated_blobs") or {}
        except Exception:
            cached_blobs = {}

        intents = []
        try:
            # Enrich payload with authoritative session_meta/cycle info from ICE when available
            if ice_client and ice_client.enabled and session_id:
                try:
                    _hydr = await ice_client.hydrate(session_id=session_id, required_blobs=["session_meta"], event_id=event_id)
                    _sm = _hydr.get("session_meta") or {}
                    # merge session_meta into payload copy
                    payload = dict(payload or {})
                    payload_session_meta = dict(payload.get("session_meta") or {})
                    payload_session_meta.update(_sm)
                    payload["session_meta"] = payload_session_meta
                    # expose convenient top-level cycle fields for intent map
                    if _sm.get("current_cycle_id"):
                        payload["current_cycle_id"] = _sm.get("current_cycle_id")
                    if _sm.get("current_cycle_meta"):
                        payload["current_cycle_meta"] = _sm.get("current_cycle_meta")
                except Exception:
                    # ignore hydrate failures and proceed with original payload
                    pass

            resolved = await resolve_multi_intent(
                payload=payload,
                cached_blobs=cached_blobs,
                stage=current_stage,
                canonical_ids=canonical_ids,
            )
            if isinstance(resolved, dict):
                intents = _flatten_resolved_intents(resolved, current_stage)
        except Exception:
            intents = []

        if not intents:
            intents = parse_intents(raw_text)

        # If a pending intent is present in session meta, run it first.
        pending_id = session_meta.get("pending_intent_id") or payload.get("pending_intent_id")
        pending_slots = session_meta.get("pending_intent_slots") if isinstance(session_meta.get("pending_intent_slots"), dict) else {}
        if pending_id:
            intents.insert(0, Intent(id=str(pending_id), slots=pending_slots))

        # If any intent targets the cart stage while we're in chat, enforce cart stage via ICE
        try:
            wants_cart = any(_intent_stage_for(it, current_stage) == "cart" for it in intents)
        except Exception:
            wants_cart = False

        if wants_cart and current_stage == "chat":
            try:
                session_id, cid, new_stage = await enforce_cart_stage(payload=payload, session_id=session_id, bot_meta=bot_meta, business_meta=business_meta, event_id=event_id, store=store, ice_client=ice_client)
                current_stage = new_stage or current_stage
            except Exception:
                pass

        stage_queue = _build_stage_queue(current_stage, intents)

        async def _execute_intent(intent: Intent) -> dict[str, Any] | None:
            nonlocal cached_blobs
            intent_id = intent.id

            if intent_id == "add_item":
                product_name = str(intent.slots.get("product_name") or "").strip()
                product_id = str(intent.slots.get("product_id") or "").strip()
                quantity = int(intent.slots.get("quantity") or 0)
                if not product_name and product_id:
                    product_name = product_id
                if product_name and quantity > 0:
                    oob, ver = await add_item(store=store, session_id=session_id, event_id=event_id, product_name=product_name, quantity=quantity)
                    if event_id:
                        try:
                            await store.set_last_event(session_id, event_id)
                        except Exception:
                            pass
                    items_count = len((oob.get("cart") or {}).get("items") or []) if oob else 0
                    return _with_trace({
                        "intent_ids": [intent_id],
                        "next_node": "build_cart",
                        "reply_text": f"Added item(s). Cart now has {items_count} item(s). What else would you like?",
                        "oob_ref": f"oob:{session_id}",
                        "oob_summary": {"items_count": items_count, "oob_version": ver},
                    })

            if intent_id == "confirm_cart":
                # Promote to order stage via ICE and persist hydrated blobs
                try:
                    new_cid, blobs = await confirm_cart_and_initiate_order(store=store, session_id=session_id, cycle_id=cid, current_stage=current_stage, event_id=event_id, ice_client=ice_client)
                    if new_cid and not cid:
                        cid = new_cid
                    try:
                        oob_cur, oob_ver = await store.get_oob(session_id)
                    except Exception:
                        oob_cur, oob_ver = {}, 0
                    return _with_trace({
                        "intent_ids": [intent_id],
                        "next_node": "order.review_order",
                        "reply_text": "Order initiated. Reply 'REVIEW ORDER' to continue.",
                        "oob_ref": f"oob:{session_id}",
                        "oob_summary": {"oob_version": oob_ver},
                    })
                except Exception:
                    return _with_trace({
                        "intent_ids": [intent_id],
                        "next_node": "cart",
                        "reply_text": "Failed to confirm cart. Try again later.",
                        "oob_ref": f"oob:{session_id}",
                        "oob_summary": {},
                    })

            if intent_id == "remove_item":
                product_name = str(intent.slots.get("product_name") or "").strip()
                if product_name:
                    oob, ver = await remove_item(store=store, session_id=session_id, product_name=product_name, event_id=event_id)
                    if event_id:
                        try:
                            await store.set_last_event(session_id, event_id)
                        except Exception:
                            pass
                    items_count = len((oob.get("cart") or {}).get("items") or []) if oob else 0
                    return _with_trace({
                        "intent_ids": [intent_id],
                        "next_node": "build_cart",
                        "reply_text": f"Removed item. Cart now has {items_count} item(s).",
                        "oob_ref": f"oob:{session_id}",
                        "oob_summary": {"items_count": items_count, "oob_version": ver},
                    })

            if intent_id == "clear_cart":
                oob, ver = await clear_cart(store=store, session_id=session_id, event_id=event_id)
                if event_id:
                    try:
                        await store.set_last_event(session_id, event_id)
                    except Exception:
                        pass
                return _with_trace({
                    "intent_ids": [intent_id],
                    "next_node": "build_cart",
                    "reply_text": "Cart cleared. What would you like to add?",
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"items_count": 0, "oob_version": ver},
                })

            if intent_id == "view_cart":
                summary = await view_cart(store=store, session_id=session_id)
                oob = summary.get("oob")
                ver = summary.get("oob_ver")
                items = (oob.get("cart") or {}).get("items") or [] if oob else []
                items_count = len(items) if isinstance(items, list) else 0
                return _with_trace({
                    "intent_ids": [intent_id],
                    "next_node": "cart.view",
                    "reply_text": f"Your cart has {items_count} item(s).",
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"items_count": items_count, "oob_version": ver},
                })

            if intent_id in ("greet_and_suggest", "greet", "greet_and_recommend"):
                # Ensure session exists and get current cycle/stage via ICE
                sid, cid, current_stage = await ensure_session_and_cycle(payload=payload, session_id=session_id, bot_meta=bot_meta, business_meta=business_meta, event_id=event_id, ice_client=ice_client)
                # Ensure local variables updated
                if sid:
                    session_id = sid

                # Execute greet_and_suggest to build a context snapshot
                res = await greet_and_suggest(store=store, session_id=session_id, event_id=event_id, ice_client=ice_client, raw_text=raw_text)
                # Build snapshot aligned to bot-session expectations
                snapshot = res.get("context_snapshot") if isinstance(res, dict) else {"user_state": {}, "diagnostics": {}, "user_text": raw_text}

                # If mapper exists, execute multi-intent mapper sequentially
                mapper = res.get("mapper") if isinstance(res, dict) else None
                mapper_results = []
                if mapper:
                    mapper_results = await execute_multi_intent_mapper(store=store, session_id=session_id, mapper=mapper, event_id=event_id, ice_client=ice_client)

                # Attempt stage upgrade if currently in chat
                new_cycle_id, ice_blobs = await upgrade_stage_if_chat(store=store, session_id=session_id, cycle_id=cid, current_stage=current_stage, snapshot=snapshot, event_id=event_id, ice_client=ice_client)
                # only adopt returned cycle id when we did not already have one
                if new_cycle_id and not cid:
                    cid = new_cycle_id

                # Merge OOB into snapshot reference for final context
                try:
                    oob_current, oob_ver = await store.get_oob(session_id)
                except Exception:
                    oob_current, oob_ver = {}, 0

                final_ctx = build_final_context(snapshot=snapshot, mapper_results=mapper_results, store_oob=oob_current)

                # Construct reply via Gemini-like call (placeholder direct call)
                # Enforce persona and light Bemba/Nyanja mix
                def _bemba_mix(text: str) -> str:
                    # Insert a short Bemba/Nyanja phrase (~10-20% of sentences)
                    phrases = ["Muli bwanji!", "Nshakubwela.", "Nomba, shani?", "Zikomo!"]
                    return text + " " + phrases[0]

                # Simple direct composition for reply (replace with real Gemini client integration)
                reply_base = res.get("reply_text") or "Hello"
                # add a small localised phrase to meet 10-20% mixing guidance
                reply_text = _bemba_mix(reply_base)

                return _with_trace({
                    "intent_ids": [intent_id],
                    "next_node": "greet_and_suggest",
                    "reply_text": reply_text,
                    "render_type": "direct_gemini",
                    "persona": "NTheemba",
                    "context": final_ctx,
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"items_count": (oob_current.get("cart") or {}).get("items") and len((oob_current.get("cart") or {}).get("items") or []) if oob_current else 0, "oob_version": oob_ver},
                })

            if intent_id in ("browse_catalogue.serve_categories", "serve_categories", "browse_categories"):
                res = await serve_categories(store=store, session_id=session_id, event_id=event_id, ice_client=ice_client)
                return _with_trace({
                    "intent_ids": [intent_id],
                    "next_node": "browse_catalogue.serve_categories",
                    "reply_text": res.get("reply_text") or "Here are some categories.",
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"items_count": (res.get("oob") or {}).get("cart") and len((res.get("oob") or {}).get("cart").get("items") or []) if res.get("oob") else 0, "oob_version": res.get("oob_ver")},
                })

            if intent_id in ("browse_catalogue.select_category", "select_category"):
                cat = str(intent.slots.get("category") or intent.slots.get("category_id") or "").strip() or None
                name = intent.slots.get("category_name") or None
                if cat:
                    oob, ver = await select_category(store=store, session_id=session_id, category_id=cat, category_name=name, event_id=event_id)
                else:
                    oob, ver = await select_category(store=store, session_id=session_id, category_name=name, event_id=event_id)
                return _with_trace({
                    "intent_ids": [intent_id],
                    "next_node": "browse_catalogue.select_category",
                    "reply_text": f"Selected category: {name or cat}",
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"items_count": (oob.get("cart") or {}).get("items") and len((oob.get("cart") or {}).get("items") or []) if oob else 0, "oob_version": ver},
                })

            if intent_id in ("browse_catalogue.serve_products", "serve_products", "browse_products"):
                # Category requested (optional)
                cat = str(intent.slots.get("category") or intent.slots.get("category_id") or "").strip() or None

                # Resolve authoritative session/stage via ICE
                try:
                    sid, cid, resolved_stage = await resolve_stage_via_ice(payload=payload, session_id=session_id, bot_meta=bot_meta, business_meta=business_meta, event_id=event_id, ice_client=ice_client)
                    if sid:
                        session_id = sid
                except Exception:
                    resolved_stage = "chat"

                # If we're still in chat stage, run greet flow first to satisfy prerequisites
                if resolved_stage == "chat":
                    try:
                        resg = await greet_and_suggest(store=store, session_id=session_id, event_id=event_id, ice_client=ice_client, raw_text=raw_text)
                        snapshot = resg.get("context_snapshot") if isinstance(resg, dict) else {"user_state": {}, "diagnostics": {}, "user_text": raw_text}
                        # Attempt upgrade to cart if ICE wants to
                        try:
                            new_cid, _ = await upgrade_stage_if_chat(store=store, session_id=session_id, cycle_id=None, current_stage="chat", snapshot=snapshot, event_id=event_id, ice_client=ice_client)
                            if new_cid:
                                cid = new_cid
                        except Exception:
                            pass
                    except Exception:
                        snapshot = {"user_state": {}, "diagnostics": {}, "user_text": raw_text}

                # Fetch and group products using ICE hydrate (authoritative blobs)
                grouped_products, categories, slots, diagnostics = await fetch_and_group_products(store=store, session_id=session_id, category_id=cat, ice_client=ice_client, event_id=event_id)

                # Merge current OOB for final context
                try:
                    oob_current, oob_ver = await store.get_oob(session_id)
                except Exception:
                    oob_current, oob_ver = {}, 0

                # Build simplified catalogue context for Gemini
                snapshot_for_ctx = {"user_text": raw_text, "user_state": {}, "diagnostics": diagnostics}
                final_ctx = build_catalogue_context(snapshot=snapshot_for_ctx, grouped_products=grouped_products, categories=categories, slots=slots, store_oob=oob_current)

                # Construct direct Gemini reply
                reply_text = "Here are the products I found for you."
                reply_text = _local_bemba_mix(reply_text)

                return _with_trace({
                    "intent_ids": [intent_id],
                    "next_node": "browse_catalogue.serve_products",
                    "reply_text": reply_text,
                    "render_type": "direct_gemini",
                    "persona": "NTheemba",
                    "context": final_ctx,
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"oob_version": oob_ver},
                })

            if intent_id in ("browse_catalogue.select_product", "select_product"):
                pid = str(intent.slots.get("product_id") or intent.slots.get("id") or "").strip() or None
                pname = intent.slots.get("product_name") or None
                if pid:
                    oob, ver = await select_product(store=store, session_id=session_id, product_id=pid, product_name=pname, event_id=event_id, ice_client=ice_client)
                else:
                    oob, ver = await select_product(store=store, session_id=session_id, product_name=pname, event_id=event_id, ice_client=ice_client)
                return _with_trace({
                    "intent_ids": [intent_id],
                    "next_node": "browse_catalogue.select_product",
                    "reply_text": f"Selected product: {pname or pid}",
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"items_count": (oob.get("cart") or {}).get("items") and len((oob.get("cart") or {}).get("items") or []) if oob else 0, "oob_version": ver},
                })

            if intent_id in ("browse_catalogue.show_product_details", "show_product_details", "product.details"):
                pid = str(intent.slots.get("product_id") or intent.slots.get("id") or "").strip() or None
                pname = intent.slots.get("product_name") or None
                try:
                    res = await show_product_details(store=store, session_id=session_id, product_id=pid, product_name=pname, event_id=event_id, ice_client=ice_client)
                    oob = res.get("oob")
                    ver = res.get("oob_ver")
                    reply_text = res.get("reply_text") or "Here are the product details."
                except Exception:
                    oob = None
                    ver = None
                    reply_text = "Failed to fetch product details. Try again later."
                return _with_trace({
                    "intent_ids": [intent_id],
                    "next_node": "browse_catalogue.show_product_details",
                    "reply_text": reply_text,
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"oob_version": ver},
                })

            if intent_id in ("order.confirm_cart", "confirm_cart"):
                # confirm cart locally
                oob, ver = await confirm_cart(store=store, session_id=session_id, event_id=event_id)
                if event_id:
                    try:
                        await store.set_last_event(session_id, event_id)
                    except Exception:
                        pass

                # resolve stage/cycle and initiate order stage in ICE
                try:
                    sid, cid, cur_stage = await resolve_stage_via_ice(payload=payload, session_id=session_id, bot_meta=bot_meta, business_meta=business_meta, event_id=event_id, ice_client=ice_client)
                    if sid:
                        session_id = sid
                except Exception:
                    cid = None
                    cur_stage = "cart"

                await confirm_cart_and_initiate_order(
                    store=store,
                    session_id=session_id,
                    cycle_id=cid,
                    current_stage=cur_stage,
                    event_id=event_id,
                    ice_client=ice_client,
                    raw_text=raw_text,
                )

                # automatic validation + review
                review, _snapshot = await validate_and_review_order(store=store, session_id=session_id, event_id=event_id, ice_client=ice_client)
                items_count = review.get("items_count") or 0
                totals = review.get("totals") or {}
                reply_text = f"Order review ready. {items_count} item(s). Total: {totals.get('grand_total')}. Reply 'CONFIRM ORDER' to continue."
                reply_text = _local_bemba_mix(reply_text)

                return _with_trace({
                    "intent_ids": [intent_id],
                    "next_node": "confirm_order_gate",
                    "reply_text": reply_text,
                    "render_type": "direct_gemini",
                    "persona": "NTheemba",
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"oob_version": ver},
                })

            if intent_id in ("order.validate_items", "validate_items"):
                oob, ver = await validate_items(store=store, session_id=session_id, event_id=event_id)
                if event_id:
                    try:
                        await store.set_last_event(session_id, event_id)
                    except Exception:
                        pass
                return _with_trace({
                    "intent_ids": [intent_id],
                    "next_node": "order.validate_items",
                    "reply_text": "Items validated.",
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"oob_version": ver},
                })

            if intent_id in ("order.check_stock", "check_stock"):
                try:
                    oob, ver = await check_stock(store=store, session_id=session_id, event_id=event_id, ice_client=ice_client)
                    reply_text = "Stock checked."
                except ValueError:
                    oob = None
                    ver = None
                    reply_text = "Inventory service not configured."
                except Exception:
                    oob = None
                    ver = None
                    reply_text = "Failed to check stock. Try again later."
                return _with_trace({
                    "intent_ids": [intent_id],
                    "next_node": "order.check_stock",
                    "reply_text": reply_text,
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"oob_version": ver},
                })

            if intent_id in ("order.calculate_total", "calculate_total"):
                try:
                    oob, ver = await calculate_total(store=store, session_id=session_id, event_id=event_id, ice_client=ice_client)
                    reply_text = "Totals calculated. Reply 'REVIEW ORDER' to continue."
                except ValueError:
                    oob = None
                    ver = None
                    reply_text = "Pricing service not configured."
                except Exception:
                    oob = None
                    ver = None
                    reply_text = "Failed to calculate totals. Try again later."
                return _with_trace({
                    "intent_ids": [intent_id],
                    "next_node": "order.calculate_total",
                    "reply_text": reply_text,
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"oob_version": ver},
                })

            if intent_id in ("order.review_order", "review_order"):
                summary = await review_order(store=store, session_id=session_id)
                oob = summary.get("oob")
                ver = summary.get("oob_ver")
                items_count = summary.get("items_count") or 0
                totals = summary.get("totals") or {}
                if summary.get("ready_to_confirm"):
                    reply_text = f"Order ready. {items_count} item(s). Total: {totals.get('grand_total')}. Reply 'CONFIRM ORDER' to place the order."
                    next_node = "confirm_order_gate"
                else:
                    reply_text = "Order summary ready. Reply 'CALCULATE TOTAL' to get authoritative totals."
                    next_node = "order.calculate_total"
                return _with_trace({
                    "intent_ids": [intent_id],
                    "next_node": next_node,
                    "reply_text": reply_text,
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"items_count": items_count, "oob_version": ver},
                })

            if intent_id in ("confirm_order", "order.confirm_order"):
                try:
                    oob, ver = await confirm_order_gate(store=store, session_id=session_id, event_id=event_id, raw_text=raw_text, ice_client=ice_client)
                    order_id = (oob.get("meta") or {}).get("order_id") if isinstance(oob, dict) else None
                    if order_id:
                        # transition to payment stage in ICE
                        try:
                            sid, cid, _cur_stage = await resolve_stage_via_ice(payload=payload, session_id=session_id, bot_meta=bot_meta, business_meta=business_meta, event_id=event_id, ice_client=ice_client)
                            if sid:
                                session_id = sid
                        except Exception:
                            cid = None
                        await transition_to_payment(store=store, session_id=session_id, cycle_id=cid, order_id=order_id, event_id=event_id, ice_client=ice_client)
                        reply_text = "Please send your mobile money number (starts with 260), delivery option (pickup or delivery), and delivery location (town + exact address)."
                    else:
                        reply_text = "Order confirmation received, but order_id is missing."
                except ValueError:
                    oob = None
                    ver = None
                    reply_text = "Order creation service not configured."
                except Exception:
                    oob = None
                    ver = None
                    reply_text = "Failed to create order. Try again later."
                reply_text = _local_bemba_mix(reply_text)
                return _with_trace({
                    "intent_ids": [intent_id],
                    "next_node": "confirm_order_gate",
                    "reply_text": reply_text,
                    "render_type": "direct_gemini",
                    "persona": "NTheemba",
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"oob_version": ver},
                })

            if intent_id in ("refund.request", "refund.collect_reason"):
                # Refund initiation flow: collect reason or record refund and notify admin.
                reason = (raw_text or "").strip()
                if not reason:
                    reply_text = "Please tell us the reason for the refund request."
                    reply_text = _local_bemba_mix(reply_text)
                    return _with_trace({
                        "intent_ids": [intent_id],
                        "next_node": "refund.collect_reason",
                        "reply_text": reply_text,
                        "render_type": "direct_gemini",
                        "persona": "NTheemba",
                        "oob_ref": f"oob:{session_id}",
                        "oob_summary": {},
                    })

                try:
                    oob, ver = await initiate_refund(store=store, session_id=session_id, event_id=event_id, raw_text=reason, ice_client=ice_client)
                    reply_text = "Refund request recorded. We've logged it and notified our admin team to investigate."
                except ValueError:
                    oob = None
                    ver = None
                    reply_text = "Refund service not configured."
                except Exception:
                    oob = None
                    ver = None
                    reply_text = "Failed to record refund request. Try again later."

                reply_text = _local_bemba_mix(reply_text)
                return _with_trace({
                    "intent_ids": [intent_id],
                    "next_node": "initiate_refund",
                    "reply_text": reply_text,
                    "render_type": "direct_gemini",
                    "persona": "NTheemba",
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"oob_version": ver},
                })

            if intent_id in ("confirm_payment", "order.confirm_payment"):
                # If user explicitly confirms payment, trigger ICE payment and transition to delivery.
                if raw_text.strip().upper() == "CONFIRM PAYMENT":
                    try:
                        oob_current, _ = await store.get_oob(session_id)
                    except Exception:
                        oob_current = {}

                    meta = oob_current.get("meta") or {}
                    order_id = meta.get("order_id")
                    payment_phone = meta.get("payment_phone")
                    delivery_option = meta.get("delivery_option")
                    delivery_location = meta.get("delivery_location") or {}
                    delivery_town = delivery_location.get("town")
                    delivery_address = delivery_location.get("address")

                    if not (order_id and payment_phone and delivery_option and delivery_town):
                        reply_text = "Please provide your mobile money number, delivery option, and delivery location before confirming payment."
                        reply_text = _local_bemba_mix(reply_text)
                        return _with_trace({
                            "intent_ids": [intent_id],
                            "next_node": "payment.collect_inputs",
                            "reply_text": reply_text,
                            "render_type": "direct_gemini",
                            "persona": "NTheemba",
                            "oob_ref": f"oob:{session_id}",
                            "oob_summary": {},
                        })

                    try:
                        oob, ver = await confirm_payment_gate(store=store, session_id=session_id, event_id=event_id, raw_text=raw_text, ice_client=ice_client)
                    except ValueError:
                        oob = None
                        ver = None
                        reply_text = "Payment service not configured."
                        reply_text = _local_bemba_mix(reply_text)
                        return _with_trace({
                            "intent_ids": [intent_id],
                            "next_node": "confirm_payment_gate",
                            "reply_text": reply_text,
                            "render_type": "direct_gemini",
                            "persona": "NTheemba",
                            "oob_ref": f"oob:{session_id}",
                            "oob_summary": {"oob_version": ver},
                        })
                    except Exception:
                        oob = None
                        ver = None
                        reply_text = "Failed to trigger payment. Try again later."
                        reply_text = _local_bemba_mix(reply_text)
                        return _with_trace({
                            "intent_ids": [intent_id],
                            "next_node": "confirm_payment_gate",
                            "reply_text": reply_text,
                            "render_type": "direct_gemini",
                            "persona": "NTheemba",
                            "oob_ref": f"oob:{session_id}",
                            "oob_summary": {"oob_version": ver},
                        })

                    # transition to delivery
                    reply = await transition_to_delivery(
                        store=store,
                        session_id=session_id,
                        cycle_id=None,
                        order_id=order_id,
                        payment_phone=payment_phone,
                        delivery_option=delivery_option,
                        delivery_town=delivery_town,
                        delivery_address=delivery_address,
                        event_id=event_id,
                        ice_client=ice_client,
                    )
                    return _with_trace({
                        "intent_ids": [intent_id],
                        "next_node": "delivery",
                        "reply_text": reply.get("text") or reply.get("reply_text") or "Payment confirmed.",
                        "render_type": "direct_gemini",
                        "persona": "NTheemba",
                        "oob_ref": f"oob:{session_id}",
                        "oob_summary": {"oob_version": ver},
                    })

                # Otherwise treat the message as a one-turn input bundle.
                available_towns = await fetch_business_delivery_locations(
                    ice_client=ice_client,
                    session_id=session_id,
                    business_id=business_meta.get("id") if isinstance(business_meta, dict) else None,
                    business_phone=(business_meta.get("phone_number") or business_meta.get("phone")) if isinstance(business_meta, dict) else None,
                    business_meta=business_meta if isinstance(business_meta, dict) else None,
                )

                inputs = await collect_payment_inputs_one_turn(payload=payload, available_towns=available_towns)
                errors = validate_payment_inputs(
                    phone=inputs.get("payment_phone"),
                    delivery_option=inputs.get("delivery_option"),
                    town=inputs.get("delivery_town"),
                    address=inputs.get("delivery_address"),
                    available_towns=available_towns,
                )

                if errors:
                    missing_fields = ", ".join(sorted(errors.keys()))
                    reply_text = f"Please provide valid {missing_fields}. Mobile money must start with 260."
                    reply_text = _local_bemba_mix(reply_text)
                    return _with_trace({
                        "intent_ids": [intent_id],
                        "next_node": "payment.collect_inputs",
                        "reply_text": reply_text,
                        "render_type": "direct_gemini",
                        "persona": "NTheemba",
                        "oob_ref": f"oob:{session_id}",
                        "oob_summary": {},
                    })

                # Persist payment inputs + snapshot in OOB
                try:
                    oob_current, _ = await store.create_default_if_missing(session_id)
                except Exception:
                    oob_current = {}

                total_price = ((oob_current.get("cart") or {}).get("totals") or {}).get("grand_total")
                order_id = (oob_current.get("meta") or {}).get("order_id")
                snapshot = {
                    "user_text": inputs.get("raw_text") or raw_text,
                    "diagnostics": {},
                    "user_state": {"stage": "payment"},
                }
                payment_context = build_payment_context(
                    snapshot=snapshot,
                    store_oob=oob_current,
                    order_id=order_id,
                    payment_phone=inputs.get("payment_phone"),
                    delivery_option=inputs.get("delivery_option"),
                    delivery_town=inputs.get("delivery_town"),
                    delivery_address=inputs.get("delivery_address"),
                    total_price=total_price,
                )

                try:
                    async def _upd(o: dict[str, Any]) -> dict[str, Any]:
                        o = dict(o)
                        meta = dict(o.get("meta") or {})
                        meta["payment_phone"] = inputs.get("payment_phone")
                        meta["delivery_option"] = inputs.get("delivery_option")
                        meta["delivery_location"] = {
                            "town": inputs.get("delivery_town"),
                            "address": inputs.get("delivery_address"),
                        }
                        meta["payment_context"] = payment_context
                        o["meta"] = meta
                        o["last_node_executed"] = "payment.collect_inputs"
                        return o

                    oob, ver = await store.cas_update(session_id, _upd)
                except Exception:
                    oob = None
                    ver = None

                reply_text = "Thanks. Reply 'CONFIRM PAYMENT' to proceed."
                reply_text = _local_bemba_mix(reply_text)
                return _with_trace({
                    "intent_ids": [intent_id],
                    "next_node": "confirm_payment_gate",
                    "reply_text": reply_text,
                    "render_type": "direct_gemini",
                    "persona": "NTheemba",
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"oob_version": ver},
                })

            if intent_id in ("payment.verify_status", "payment.verify", "verify_payment"):
                try:
                    oob, ver = await verify_payment_status(store=store, session_id=session_id, event_id=event_id, ice_client=ice_client)
                    reply_text = "Payment status checked."
                except ValueError:
                    oob = None
                    ver = None
                    reply_text = "Payment status service not configured."
                except Exception:
                    oob = None
                    ver = None
                    reply_text = "Failed to verify payment status. Try again later."
                return _with_trace({
                    "intent_ids": [intent_id],
                    "next_node": "payment.verify_status",
                    "reply_text": reply_text,
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"oob_version": ver},
                })

            if intent_id in ("fulfillment.choose_method", "fulfillment.choose", "choose_fulfillment"):
                method = str(intent.slots.get("method") or intent.slots.get("fulfillment_method") or "").strip() or None
                details = {}
                for k in ("location", "window", "address", "pickup_location"):
                    if intent.slots.get(k) is not None:
                        details[k] = intent.slots.get(k)
                try:
                    oob, ver = await choose_method(store=store, session_id=session_id, method=method, details=(details or None), event_id=event_id, ice_client=ice_client)
                    reply_text = "Fulfillment method saved."
                except ValueError:
                    oob = None
                    ver = None
                    reply_text = "Fulfillment validation service not configured."
                except Exception:
                    oob = None
                    ver = None
                    reply_text = "Failed to set fulfillment method. Try again later."
                return _with_trace({
                    "intent_ids": [intent_id],
                    "next_node": "fulfillment.choose_method",
                    "reply_text": reply_text,
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"oob_version": ver},
                })

            if intent_id in ("fulfillment.select_delivery_option", "select_delivery_option"):
                method = str(intent.slots.get("method") or intent.slots.get("fulfillment_type") or "").strip() or None
                details = intent.slots.get("details") or None
                oob, ver = await select_delivery_option(store=store, session_id=session_id, method=method, details=details, event_id=event_id)
                return _with_trace({
                    "intent_ids": [intent_id],
                    "next_node": "fulfillment.select_delivery_option",
                    "reply_text": f"Set fulfillment to {method}.",
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"oob_version": ver},
                })

            if intent_id in ("fulfillment.choose_location", "choose_location"):
                address = intent.slots.get("address") or None
                pickup = intent.slots.get("pickup_location") or None
                oob, ver = await choose_location(store=store, session_id=session_id, address=address, pickup_location=pickup, event_id=event_id)
                return _with_trace({
                    "intent_ids": [intent_id],
                    "next_node": "fulfillment.choose_location",
                    "reply_text": "Saved delivery/pickup location.",
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"oob_version": ver},
                })

            if intent_id in ("affiliate.capture_code", "capture_affiliate"):
                code = intent.slots.get("affiliate_code") or None
                source = intent.slots.get("affiliate_source") or None
                payload_ref = payload or None
                oob, ver = await capture_code(store=store, session_id=session_id, affiliate_code=code, source=source, payload=payload_ref, event_id=event_id)
                return _with_trace({
                    "intent_ids": [intent_id],
                    "next_node": "affiliate.capture_code",
                    "reply_text": "Thanks — I noted your code.",
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"oob_version": ver},
                })

            if intent_id in ("affiliate.track_click", "track_affiliate"):
                try:
                    oob, ver = await track_click(store=store, session_id=session_id, event_id=event_id, ice_client=ice_client)
                    reply_text = "Recorded affiliate click."
                except ValueError:
                    oob = None
                    ver = None
                    reply_text = "Tracking service not configured."
                except Exception:
                    oob = None
                    ver = None
                    reply_text = "Failed to record affiliate click."
                return _with_trace({
                    "intent_ids": [intent_id],
                    "next_node": "affiliate.track_click",
                    "reply_text": reply_text,
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"oob_version": ver},
                })

            if intent_id in ("inspect_item", "cart.inspect_item"):
                product_name = str(intent.slots.get("product_name") or "").strip() or None
                line_index = intent.slots.get("line_index")
                summary = await inspect_item(store=store, session_id=session_id, product_name=product_name, line_index=line_index)
                oob = summary.get("oob")
                ver = summary.get("oob_ver")
                if summary.get("found"):
                    item = summary.get("item") or {}
                    pname = item.get("product_name") or "item"
                    qty = item.get("quantity") or item.get("qty") or 1
                    reply_text = f"{pname}: quantity {qty}. Reply 'remove {pname}' to remove it."
                else:
                    reply_text = "Item not found in your cart."
                return _with_trace({
                    "intent_ids": [intent_id],
                    "next_node": "cart.inspect_item",
                    "reply_text": reply_text,
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"oob_version": ver},
                })

            if intent_id == "help":
                return _with_trace({
                    "intent_ids": [intent_id],
                    "next_node": "help",
                    "reply_text": help_text(),
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {},
                })

            if intent_id == "cancel":
                res = await cancel_flow(store=store, session_id=session_id, event_id=event_id)
                reply_text = res.get("reply_text") if isinstance(res, dict) else "Cancelled."
                return _with_trace({
                    "intent_ids": [intent_id],
                    "next_node": "cancel",
                    "reply_text": reply_text,
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"oob_version": res.get("oob_ver") if isinstance(res, dict) else None},
                })

            if intent_id.startswith("fallback") or intent_id == "unknown":
                reply_text = fallback_reply(raw_text)
                return _with_trace({
                    "intent_ids": [intent_id],
                    "next_node": "help",
                    "reply_text": reply_text,
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {},
                })

            return None

        last_result = None
        # Execution diagnostics and executed-intent tracking
        exec_diagnostics: dict = {"missing": [], "notes": []}
        executed_intents: list[str] = []

        for st in stage_queue:
            await _hydrate_stage_context(store=store, session_id=session_id, stage=st, ice_client=ice_client, event_id=event_id)
            # select intents that map to this stage (respect explicit __stage hints)
            stage_intents = [i for i in intents if _intent_stage_for(i, current_stage) == st]

            # Filter out non-canonical intents and record diagnostics
            canonical_for_stage = _canonical_ids_for_stage(st)
            valid_stage_intents: list[Intent] = []
            for it in stage_intents:
                if it.id not in canonical_for_stage:
                    exec_diagnostics.setdefault("missing", []).append(f"invalid_intent:{it.id}@{st}")
                    exec_diagnostics.setdefault("notes", []).append(f"Rejected non-canonical intent '{it.id}' for stage '{st}'")
                    continue
                valid_stage_intents.append(it)

            # enforce global prerequisites using OOB + executed intents
            try:
                oob, _ver_check = await store.create_default_if_missing(session_id)
            except Exception:
                oob = {}

            # Greeting required before cart creation
            if st == "cart":
                greeted = bool(session_meta.get("has_greeted") or session_meta.get("greeted") or any(x in ("greet_and_suggest","greet") for x in executed_intents))
                if not greeted and any(it.id.startswith("add") or it.id in ("add_item",) for it in valid_stage_intents):
                    exec_diagnostics.setdefault("missing", []).append("prereq:greet_required_for_cart")
                    exec_diagnostics.setdefault("notes", []).append("Skipped cart intents until greeting occurs")
                    # skip executing cart intents this turn
                    continue

            # Cart must exist before order confirmation
            if st == "order":
                cart_items = (oob.get("cart") or {}).get("items") if isinstance(oob.get("cart"), dict) else None
                cart_has_items = isinstance(cart_items, list) and len(cart_items) > 0
                will_add_items = any(it.id in ("add_item",) for it in valid_stage_intents)
                if not cart_has_items and not will_add_items:
                    # If order-stage intents include confirm_order without a cart, reject
                    if any(it.id in ("confirm_order","order.confirm_cart") for it in valid_stage_intents):
                        exec_diagnostics.setdefault("missing", []).append("prereq:cart_required_for_order_confirmation")
                        exec_diagnostics.setdefault("notes", []).append("Rejected order confirmation because no cart exists")
                        # remove confirm intents from execution
                        valid_stage_intents = [it for it in valid_stage_intents if it.id not in ("confirm_order","order.confirm_cart")]

            # Order confirmation required before payment
            if st == "payment":
                order_blob = oob.get("order") if isinstance(oob.get("order"), dict) else {}
                order_confirmed = bool(order_blob.get("confirmed") or order_blob.get("status") == "confirmed" or order_blob.get("id"))
                if not order_confirmed and any(it.id in ("confirm_payment","payment.verify_status") for it in valid_stage_intents):
                    exec_diagnostics.setdefault("missing", []).append("prereq:order_confirmation_required_for_payment")
                    exec_diagnostics.setdefault("notes", []).append("Rejected payment intents until order is confirmed")
                    valid_stage_intents = [it for it in valid_stage_intents if it.id not in ("confirm_payment","payment.verify_status")]

            # Payment confirmation required before delivery
            if st == "delivery":
                payment_blob = oob.get("payment") if isinstance(oob.get("payment"), dict) else {}
                payment_confirmed = bool(payment_blob.get("confirmed") or payment_blob.get("status") == "confirmed")
                if not payment_confirmed and any(it.id.startswith("confirm_payment") or it.id == "confirm_payment" for it in valid_stage_intents):
                    exec_diagnostics.setdefault("missing", []).append("prereq:payment_required_for_delivery")
                    exec_diagnostics.setdefault("notes", []).append("Rejected delivery intents until payment is confirmed")
                    valid_stage_intents = [it for it in valid_stage_intents if not (it.id.startswith("confirm_payment") or it.id == "confirm_payment")]

            # missing required slots check (if still valid intents remain)
            missing = _missing_required_slots(st, valid_stage_intents, session_meta)
            if missing:
                exec_diagnostics.setdefault("missing", []).extend([f"missing_slot:{m}" for m in missing])
                payload = {
                    "intent_ids": [i.id for i in valid_stage_intents] if valid_stage_intents else [],
                    "next_node": f"{st}.missing_slots",
                    "reply_text": _missing_slots_prompt(st, missing),
                    "render_type": "nlg",
                    "template_id": "chat.stage.reply",
                    "template_vars": {
                        "stage": st,
                        "sub_stage": "missing_slots",
                        "session_id": session_id,
                        "bot_name": bot_meta.get("persona_name") or bot_meta.get("name") or None,
                        "business_name": business_meta.get("name") or None,
                        "is_returning": session_meta.get("is_returning"),
                        "locale": (session_meta.get("locale") or payload.get("locale") or "en"),
                        "timezone": session_meta.get("timezone"),
                        "missing_slots": missing,
                        "cta_labels": ["Help"],
                    },
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {},
                }
                # If render_type==nlg, try to generate the polished reply_text via Gemini NLG.
                if payload.get("render_type") == "nlg":
                    try:
                        tpl_id = payload.get("template_id")
                        tpl_vars = payload.get("template_vars") or {}
                        text = await render_reply(tpl_id, tpl_vars)
                        if isinstance(text, str) and text.strip():
                            payload["reply_text"] = text.strip()
                    except Exception:
                        pass
                # attach diagnostics
                payload.setdefault("diagnostics", {}).setdefault("missing", [])
                payload["diagnostics"]["missing"].extend(exec_diagnostics.get("missing", []))
                payload["diagnostics"].setdefault("notes", [])
                payload["diagnostics"]["notes"].extend(exec_diagnostics.get("notes", []))
                return _with_trace(payload)

            # Execute valid intents for this stage
            for intent in valid_stage_intents:
                res = await _execute_intent(intent)
                if res:
                    executed_intents.extend(res.get("intent_ids") or [])
                    last_result = res

        if last_result:
            # attach any execution diagnostics before returning
            last_result.setdefault("diagnostics", {}).setdefault("missing", [])
            last_result["diagnostics"]["missing"].extend(exec_diagnostics.get("missing", []))
            last_result.setdefault("diagnostics", {}).setdefault("notes", [])
            last_result["diagnostics"]["notes"].extend(exec_diagnostics.get("notes", []))
            # Build updated context snapshot for NLG
            try:
                latest_oob, _ver2 = await store.create_default_if_missing(session_id)
            except Exception:
                latest_oob = {}

            cart_items = (latest_oob.get("cart") or {}).get("items") or []
            order_blob = latest_oob.get("order") or {}
            payment_blob = latest_oob.get("payment") or {}

            user_state = {
                "stage": current_stage,
                "cart_items": cart_items,
                "order_status": order_blob.get("status") or order_blob.get("state") or None,
                "payment_status": payment_blob.get("status") or None,
                "user_text": raw_text,
            }

            diagnostics_summary = last_result.get("diagnostics") or {"missing": [], "notes": []}

            # Generate reply via NLG template using current context
            reply_text = last_result.get("reply_text") or ""
            next_questions: list[str] = []
            if diagnostics_summary.get("missing"):
                for m in diagnostics_summary.get("missing"):
                    # simple mapping of missing slots to clarifying questions
                    if m.startswith("missing_slot:"):
                        slot = m.split(":", 1)[1]
                        next_questions.append(f"Please provide {slot}.")
                    elif m.startswith("prereq:"):
                        next_questions.append("Please follow the required step before continuing.")
                    else:
                        next_questions.append("Please clarify.")
                # prefer a clarifying reply
                try:
                    tpl_vars = {"user_state": user_state, "diagnostics": diagnostics_summary}
                    text = await render_reply("chat.clarify", tpl_vars)
                    if isinstance(text, str) and text.strip():
                        reply_text = text.strip()
                except Exception:
                    reply_text = reply_text or "I need a bit more information to continue."
            else:
                # progression valid — confirm next step
                try:
                    tpl_vars = {"user_state": user_state, "diagnostics": diagnostics_summary}
                    text = await render_reply("chat.confirm_next", tpl_vars)
                    if isinstance(text, str) and text.strip():
                        reply_text = text.strip()
                except Exception:
                    reply_text = reply_text or "Done. What would you like to do next?"

            last_result["reply"] = reply_text
            last_result["next_questions"] = next_questions
            return last_result

    # Build cached blobs context for Gemini-based multi-intent resolution.
    cached_blobs: dict[str, Any] = {}
    store = OOBStore()
    if session_id:
        try:
            oob, _ver = await store.create_default_if_missing(session_id)
            meta = oob.get("meta") or {}
            cached_blobs = meta.get("hydrated_blobs") or {}
        except Exception:
            cached_blobs = {}

    stage = _extract_stage(payload, session_meta)
    canonical_ids = _canonical_ids_for_stage(stage)

    # Use the handler-based Gemini resolver; fallback to deterministic parse if empty.
    try:
        resolved = await resolve_multi_intent(
            payload=payload,
            cached_blobs=cached_blobs,
            stage=stage,
            canonical_ids=canonical_ids,
        )
        intents_raw = resolved.get("intents") if isinstance(resolved, dict) else None
        if isinstance(intents_raw, list) and intents_raw:
            for it in intents_raw:
                if isinstance(it, dict) and it.get("id"):
                    intents.append(Intent(id=str(it.get("id")), slots=it.get("slots") or {}))
        if not intents:
            intents = parse_intents(raw_text)
    except Exception:
        intents = parse_intents(raw_text)

    async def _instrumented_call(node_name: str, func, *f_args, **f_kwargs):
        r = getattr(store, "_r", None)
        start = time.monotonic()
        span_id = str(uuid.uuid4())
        enter_payload = {
            "node": node_name,
            "intent_ids": [i.id for i in intents],
            "session_id": session_id,
            "event_id": event_id,
            "trace_id": trace_id,
            "span_id": span_id,
        }
        try:
            if r is not None:
                try:
                    # schedule non-blocking telemetry writes
                    asyncio.create_task(emit_event(r, "node_enter", enter_payload))
                    asyncio.create_task(incr_metric(r, f"node.{node_name}.calls"))
                except Exception:
                    pass

            res = await func(*f_args, **f_kwargs)

            duration = time.monotonic() - start
            exit_payload = dict(enter_payload)
            exit_payload.update({"duration_ms": int(duration * 1000), "success": True})
            if r is not None:
                try:
                    asyncio.create_task(emit_event(r, "node_exit", exit_payload))
                except Exception:
                    pass

            return res
        except Exception as exc:
            duration = time.monotonic() - start
            exit_payload = dict(enter_payload)
            exit_payload.update({"duration_ms": int(duration * 1000), "success": False, "error": str(exc), "trace": traceback.format_exc()})
            if r is not None:
                try:
                    asyncio.create_task(emit_event(r, "node_exit", exit_payload))
                    asyncio.create_task(incr_metric(r, f"node.{node_name}.errors"))
                except Exception:
                    pass
            raise

        if not session_id:
            return _with_trace({
                "intent_ids": [i.id for i in intents],
                "next_node": "help",
                "reply_text": "Missing session_id; cannot continue.",
                "oob_ref": None,
                "oob_summary": {},
            })

    # construct ICE client; if ICE_BASE_URL is not configured IceClient.enabled==False
    ice = IceClient()
    ice_client = ice if ice.enabled else None

    last_oob = None
    last_ver = None

    for intent in intents:
        if intent.id == "add_item":
            product_name = str(intent.slots.get("product_name") or "").strip()
            quantity = int(intent.slots.get("quantity") or 0)
            if product_name and quantity > 0:
                last_oob, last_ver = await _instrumented_call(
                    "add_item",
                    add_item,
                    store=store,
                    session_id=session_id,
                    event_id=event_id,
                    product_name=product_name,
                    quantity=quantity,
                )
                # persist last_event for auditability
                try:
                    if event_id:
                        await store.set_last_event(session_id, event_id)
                except Exception:
                    pass
        elif intent.id == "remove_item":
            product_name = str(intent.slots.get("product_name") or "").strip()
            if product_name:
                last_oob, last_ver = await _instrumented_call("remove_item", remove_item, store=store, session_id=session_id, product_name=product_name, event_id=event_id)
                try:
                    if event_id:
                        await store.set_last_event(session_id, event_id)
                except Exception:
                    pass
        elif intent.id == "clear_cart":
            last_oob, last_ver = await _instrumented_call("clear_cart", clear_cart, store=store, session_id=session_id, event_id=event_id)
            try:
                if event_id:
                    await store.set_last_event(session_id, event_id)
            except Exception:
                pass
        elif intent.id == "view_cart":
            summary = await _instrumented_call("view_cart", view_cart, store=store, session_id=session_id)
            last_oob = summary.get("oob")
            last_ver = summary.get("oob_ver")
        elif intent.id in ("order.confirm_cart", "confirm_cart"):
            res = await _execute_intent(intent)
            if res:
                return _with_trace(res)
        elif intent.id in ("order.validate_items", "validate_items"):
            last_oob, last_ver = await _instrumented_call("validate_items", validate_items, store=store, session_id=session_id, event_id=event_id)
            try:
                if event_id:
                    await store.set_last_event(session_id, event_id)
            except Exception:
                pass
        elif intent.id in ("order.check_stock", "check_stock"):
            try:
                last_oob, last_ver = await _instrumented_call("check_stock", check_stock, store=store, session_id=session_id, event_id=event_id, ice_client=ice_client)
                try:
                    if event_id:
                        await store.set_last_event(session_id, event_id)
                except Exception:
                    pass
            except ValueError:
                return _with_trace({
                    "intent_ids": [i.id for i in intents],
                    "next_node": "order.check_stock",
                    "reply_text": "Inventory service not configured.",
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"oob_version": last_ver if 'last_ver' in locals() else None},
                })
            except Exception:
                return _with_trace({
                    "intent_ids": [i.id for i in intents],
                    "next_node": "order.check_stock",
                    "reply_text": "Failed to check stock. Try again later.",
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"oob_version": last_ver if 'last_ver' in locals() else None},
                })
        elif intent.id in ("order.calculate_total", "calculate_total"):
            # attempt authoritative pricing via ICE if configured
            try:
                # runtime does not construct an ICE client yet; handlers expect an `ice_client` param.
                # If ICE is not configured, the handler will raise ValueError and we fall back.
                last_oob, last_ver = await _instrumented_call("calculate_total", calculate_total, store=store, session_id=session_id, event_id=event_id, ice_client=ice_client)
            except ValueError:
                return _with_trace({
                    "intent_ids": [i.id for i in intents],
                    "next_node": "order.calculate_total",
                    "reply_text": "Pricing service not configured. I can still review the order but totals are not authoritative.",
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"items_count": (last_oob.get("cart") or {}).get("items") and len((last_oob.get("cart") or {}).get("items") or []) if last_oob else 0, "oob_version": last_ver},
                })
            except Exception:
                return _with_trace({
                    "intent_ids": [i.id for i in intents],
                    "next_node": "order.calculate_total",
                    "reply_text": "Failed to calculate totals. Try again later.",
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"items_count": (last_oob.get("cart") or {}).get("items") and len((last_oob.get("cart") or {}).get("items") or []) if last_oob else 0, "oob_version": last_ver},
                })
        elif intent.id in ("inspect_item", "cart.inspect_item"):
            product_name = str(intent.slots.get("product_name") or "").strip() or None
            line_index = intent.slots.get("line_index")
            summary = await _instrumented_call("inspect_item", inspect_item, store=store, session_id=session_id, product_name=product_name, line_index=line_index)
            last_oob = summary.get("oob")
            last_ver = summary.get("oob_ver")
            # short-circuit reply with item details
            if summary.get("found"):
                item = summary.get("item") or {}
                pname = item.get("product_name") or "item"
                qty = item.get("quantity") or item.get("qty") or 1
                reply_text = f"{pname}: quantity {qty}. Reply 'remove {pname}' to remove it." 
            else:
                reply_text = "Item not found in your cart."
            return _with_trace({
                "intent_ids": [i.id for i in intents],
                "next_node": "cart.inspect_item",
                "reply_text": reply_text,
                "oob_ref": f"oob:{session_id}",
                "oob_summary": {"items_count": (last_oob.get("cart") or {}).get("items") and len((last_oob.get("cart") or {}).get("items") or []) if last_oob else 0, "oob_version": last_ver},
            })
        elif intent.id in ("order.review_order", "review_order"):
            summary = await _instrumented_call("review_order", review_order, store=store, session_id=session_id)
            last_oob = summary.get("oob")
            last_ver = summary.get("oob_ver")
            items_count = summary.get("items_count") or 0
            totals = summary.get("totals") or {}
            if summary.get("ready_to_confirm"):
                reply_text = f"Order ready. {items_count} item(s). Total: {totals.get('grand_total')}. Reply 'CONFIRM ORDER' to place the order."
                next_node = "confirm_order_gate"
            else:
                if items_count == 0:
                    reply_text = "Your cart is empty. Add items before reviewing the order."
                else:
                    reply_text = "Order summary ready but totals are missing. Reply 'CALCULATE TOTAL' to get authoritative totals."
                next_node = "order.calculate_total"
            return _with_trace({
                "intent_ids": [i.id for i in intents],
                "next_node": next_node,
                "reply_text": reply_text,
                "oob_ref": f"oob:{session_id}",
                "oob_summary": {"items_count": items_count, "oob_version": last_ver},
            })
        elif intent.id in ("confirm_order", "order.confirm_order"):
            res = await _execute_intent(intent)
            if res:
                return _with_trace(res)
        elif intent.id in ("confirm_payment", "order.confirm_payment"):
            res = await _execute_intent(intent)
            if res:
                return _with_trace(res)
        elif intent.id in ("payment.verify_status", "payment.verify", "verify_payment"):
            try:
                last_oob, last_ver = await _instrumented_call("verify_payment_status", verify_payment_status, store=store, session_id=session_id, event_id=event_id, ice_client=ice_client)
                try:
                    if event_id:
                        await store.set_last_event(session_id, event_id)
                except Exception:
                    pass
            except ValueError:
                return _with_trace({
                    "intent_ids": [i.id for i in intents],
                    "next_node": "payment.verify_status",
                    "reply_text": "Payment status service not configured.",
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"oob_version": last_ver if 'last_ver' in locals() else None},
                })
            except Exception:
                return _with_trace({
                    "intent_ids": [i.id for i in intents],
                    "next_node": "payment.verify_status",
                    "reply_text": "Failed to verify payment status. Try again later.",
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"oob_version": last_ver if 'last_ver' in locals() else None},
                })
            except Exception:
                return {
                    "intent_ids": [i.id for i in intents],
                    "next_node": "payment.verify_status",
                    "reply_text": "Failed to verify payment status. Try again later.",
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"oob_version": last_ver if 'last_ver' in locals() else None},
                }
        elif intent.id in ("fulfillment.choose_method", "fulfillment.choose", "choose_fulfillment"):
            # pick method from slots; details may include window/location/address
            method = str(intent.slots.get("method") or intent.slots.get("fulfillment_method") or "").strip() or None
            details = {}
            for k in ("location", "window", "address", "pickup_location"):
                if intent.slots.get(k) is not None:
                    details[k] = intent.slots.get(k)
            try:
                last_oob, last_ver = await _instrumented_call("choose_method", choose_method, store=store, session_id=session_id, method=method, details=(details or None), event_id=event_id, ice_client=ice_client)
                try:
                    if event_id:
                        await store.set_last_event(session_id, event_id)
                except Exception:
                    pass
            except ValueError:
                return _with_trace({
                    "intent_ids": [i.id for i in intents],
                    "next_node": "fulfillment.choose_method",
                    "reply_text": "Fulfillment validation service not configured.",
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"oob_version": last_ver if 'last_ver' in locals() else None},
                })
            except Exception:
                return _with_trace({
                    "intent_ids": [i.id for i in intents],
                    "next_node": "fulfillment.choose_method",
                    "reply_text": "Failed to set fulfillment method. Try again later.",
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"oob_version": last_ver if 'last_ver' in locals() else None},
                })
            except Exception:
                return {
                    "intent_ids": [i.id for i in intents],
                    "next_node": "confirm_payment_gate",
                    "reply_text": "Failed to trigger payment. Try again later.",
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"items_count": (last_oob.get("cart") or {}).get("items") and len((last_oob.get("cart") or {}).get("items") or []) if last_oob else 0, "oob_version": last_ver},
                }
        elif intent.id in ("fulfillment.select_delivery_option", "select_delivery_option"):
            method = str(intent.slots.get("method") or intent.slots.get("fulfillment_type") or "").strip() or None
            details = intent.slots.get("details") or None
            last_oob, last_ver = await _instrumented_call("select_delivery_option", select_delivery_option, store=store, session_id=session_id, method=method, details=details, event_id=event_id)
            try:
                if event_id:
                    await store.set_last_event(session_id, event_id)
            except Exception:
                pass
            return _with_trace({
                "intent_ids": [i.id for i in intents],
                "next_node": "fulfillment.select_delivery_option",
                "reply_text": f"Set fulfillment to {method}.",
                "oob_ref": f"oob:{session_id}",
                "oob_summary": {"oob_version": last_ver},
            })
        elif intent.id in ("fulfillment.choose_location", "choose_location"):
            address = intent.slots.get("address") or None
            pickup = intent.slots.get("pickup_location") or None
            last_oob, last_ver = await _instrumented_call("choose_location", choose_location, store=store, session_id=session_id, address=address, pickup_location=pickup, event_id=event_id)
            try:
                if event_id:
                    await store.set_last_event(session_id, event_id)
            except Exception:
                pass
            return _with_trace({
                "intent_ids": [i.id for i in intents],
                "next_node": "fulfillment.choose_location",
                "reply_text": "Saved delivery/pickup location.",
                "oob_ref": f"oob:{session_id}",
                "oob_summary": {"oob_version": last_ver},
            })
        elif intent.id in ("affiliate.capture_code", "capture_affiliate"):
            # capture affiliate code from slots or payload
            code = intent.slots.get("affiliate_code") or None
            source = intent.slots.get("affiliate_source") or None
            payload_ref = payload or None
            last_oob, last_ver = await _instrumented_call("capture_code", capture_code, store=store, session_id=session_id, affiliate_code=code, source=source, payload=payload_ref, event_id=event_id)
            try:
                if event_id:
                    await store.set_last_event(session_id, event_id)
            except Exception:
                pass
            return _with_trace({
                "intent_ids": [i.id for i in intents],
                "next_node": "affiliate.capture_code",
                "reply_text": "Thanks — I noted your code.",
                "oob_ref": f"oob:{session_id}",
                "oob_summary": {"oob_version": last_ver},
            })
        elif intent.id in ("affiliate.track_click", "track_affiliate"):
            try:
                last_oob, last_ver = await _instrumented_call("track_click", track_click, store=store, session_id=session_id, event_id=event_id, ice_client=ice_client)
                try:
                    if event_id:
                        await store.set_last_event(session_id, event_id)
                except Exception:
                    pass
            except ValueError:
                return _with_trace({
                    "intent_ids": [i.id for i in intents],
                    "next_node": "affiliate.track_click",
                    "reply_text": "Tracking service not configured.",
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"oob_version": last_ver if 'last_ver' in locals() else None},
                })
            except Exception:
                return _with_trace({
                    "intent_ids": [i.id for i in intents],
                    "next_node": "affiliate.track_click",
                    "reply_text": "Failed to record affiliate click.",
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"oob_version": last_ver if 'last_ver' in locals() else None},
                })
        elif intent.id in ("help", "confirm_order", "confirm_payment"):
            # Not implemented yet; handled via reply selection below.
            if intent.id == "help":
                # short-circuit: immediate reply
                return _with_trace({
                    "intent_ids": [i.id for i in intents],
                    "next_node": "help",
                    "reply_text": help_text(),
                    "oob_ref": f"oob:{session_id}" if session_id else None,
                    "oob_summary": {"items_count": (last_oob.get("cart") or {}).get("items") and len((last_oob.get("cart") or {}).get("items") or []) if last_oob else 0, "oob_version": last_ver},
                })
            pass
        elif intent.id in ("greet_and_suggest", "greet", "greet_and_recommend"):
            # Greet handler: ensure OOB and optionally fetch ICE recommendations
            res = await _instrumented_call("greet_and_suggest", greet_and_suggest, store=store, session_id=session_id, event_id=event_id, ice_client=ice_client, raw_text=raw_text)
            recs = res.get("recommendations") if isinstance(res, dict) else None
            suggestions = []
            if isinstance(recs, list):
                for it in recs[:3]:
                    if not isinstance(it, dict):
                        continue
                    name = it.get("title") or it.get("product_name") or it.get("name") or it.get("id")
                    if not name:
                        continue
                    suggestions.append(
                        {
                            "id": it.get("id"),
                            "name": str(name),
                            "price": it.get("price") or it.get("amount"),
                            "currency": it.get("currency"),
                        }
                    )
            play_label = f"Play with {suggestions[0]['name']}" if suggestions else "Play with a product"
            # `res` contains keys: oob, oob_ver, reply_text
            return _with_trace({
                "intent_ids": [i.id for i in intents],
                "next_node": "greet_and_suggest",
                "reply_text": res.get("reply_text") or "Hi",
                "render_type": "nlg",
                "template_id": "chat.stage.reply",
                "template_vars": {
                    "stage": "chat",
                    "sub_stage": "greeting",
                    "session_id": session_id,
                    "bot_name": bot_meta.get("persona_name") or bot_meta.get("name") or None,
                    "business_name": business_meta.get("name") or None,
                    "is_returning": session_meta.get("is_returning"),
                    "locale": (session_meta.get("locale") or payload.get("locale") or "en"),
                    "timezone": session_meta.get("timezone"),
                    "product_suggestions": suggestions,
                    "cta_labels": [play_label, "Explore offers", "Help"],
                },
                "oob_ref": f"oob:{session_id}",
                "oob_summary": {"items_count": (res.get("oob") or {}).get("cart") and len((res.get("oob") or {}).get("cart").get("items") or []) if res.get("oob") else 0, "oob_version": res.get("oob_ver")},
            })
        elif intent.id in ("browse_catalogue.serve_categories", "serve_categories", "browse_categories"):
            # Browse categories: read from cache or ask ICE for categories
            res = await _instrumented_call("serve_categories", serve_categories, store=store, session_id=session_id, event_id=event_id, ice_client=ice_client)
            return _with_trace({
                "intent_ids": [i.id for i in intents],
                "next_node": "browse_catalogue.serve_categories",
                "reply_text": res.get("reply_text") or "Here are some categories.",
                "oob_ref": f"oob:{session_id}",
                "oob_summary": {"items_count": (res.get("oob") or {}).get("cart") and len((res.get("oob") or {}).get("cart").get("items") or []) if res.get("oob") else 0, "oob_version": res.get("oob_ver")},
            })
        elif intent.id in ("browse_catalogue.select_category", "select_category"):
            # Persist selection into OOB
            cat = str(intent.slots.get("category") or intent.slots.get("category_id") or "").strip() or None
            name = intent.slots.get("category_name") or None
            if cat:
                last_oob, last_ver = await _instrumented_call("select_category", select_category, store=store, session_id=session_id, category_id=cat, category_name=name, event_id=event_id)
            else:
                # if no category id provided, still allow name
                last_oob, last_ver = await _instrumented_call("select_category", select_category, store=store, session_id=session_id, category_name=name, event_id=event_id)
            return {
                "intent_ids": [i.id for i in intents],
                "next_node": "browse_catalogue.select_category",
                "reply_text": f"Selected category: {name or cat}",
                "oob_ref": f"oob:{session_id}",
                "oob_summary": {"items_count": (last_oob.get("cart") or {}).get("items") and len((last_oob.get("cart") or {}).get("items") or []) if last_oob else 0, "oob_version": last_ver},
            }
        elif intent.id in ("browse_catalogue.serve_products", "serve_products", "browse_products"):
            # Show products for a category either from OOB selection or intent slot
            cat = str(intent.slots.get("category") or intent.slots.get("category_id") or "").strip() or None
            res = await _instrumented_call("serve_products", serve_products, store=store, session_id=session_id, category_id=cat, event_id=event_id, ice_client=ice_client)
            return {
                "intent_ids": [i.id for i in intents],
                "next_node": "browse_catalogue.serve_products",
                "reply_text": res.get("reply_text") or "Here are the products.",
                "oob_ref": f"oob:{session_id}",
                "oob_summary": {"items_count": (res.get("oob") or {}).get("cart") and len((res.get("oob") or {}).get("cart").get("items") or []) if res.get("oob") else 0, "oob_version": res.get("oob_ver")},
            }
        elif intent.id in ("browse_catalogue.select_product", "select_product"):
            pid = str(intent.slots.get("product_id") or intent.slots.get("id") or "").strip() or None
            pname = intent.slots.get("product_name") or None
            if pid:
                last_oob, last_ver = await _instrumented_call("select_product", select_product, store=store, session_id=session_id, product_id=pid, product_name=pname, event_id=event_id, ice_client=ice_client)
            else:
                last_oob, last_ver = await _instrumented_call("select_product", select_product, store=store, session_id=session_id, product_name=pname, event_id=event_id, ice_client=ice_client)
            return {
                "intent_ids": [i.id for i in intents],
                "next_node": "browse_catalogue.select_product",
                "reply_text": f"Selected product: {pname or pid}",
                "oob_ref": f"oob:{session_id}",
                "oob_summary": {"items_count": (last_oob.get("cart") or {}).get("items") and len((last_oob.get("cart") or {}).get("items") or []) if last_oob else 0, "oob_version": last_ver},
            }
        elif intent.id in ("browse_catalogue.show_product_details", "show_product_details", "product.details"):
            pid = str(intent.slots.get("product_id") or intent.slots.get("id") or "").strip() or None
            pname = intent.slots.get("product_name") or None
            try:
                res = await _instrumented_call("show_product_details", show_product_details, store=store, session_id=session_id, product_id=pid, product_name=pname, event_id=event_id, ice_client=ice_client)
                last_oob = res.get("oob")
                last_ver = res.get("oob_ver")
                reply_text = res.get("reply_text") or "Here are the product details."
            except Exception:
                reply_text = "Failed to fetch product details. Try again later."
            return {
                "intent_ids": [i.id for i in intents],
                "next_node": "browse_catalogue.show_product_details",
                "reply_text": reply_text,
                "oob_ref": f"oob:{session_id}",
                "oob_summary": {"oob_version": last_ver},
            }
        else:
            logger.info("unhandled_intent", extra={"intent_id": intent.id})

    if last_oob is None:
        # Ensure default OOB exists and fetch for reply composition.
        last_oob, last_ver = await store.create_default_if_missing(session_id)

    items = (last_oob.get("cart") or {}).get("items") or []
    items_count = len(items) if isinstance(items, list) else 0

    intent_ids = [i.id for i in intents]

    if "add_item" in intent_ids:
        reply_text = f"Added item(s). Cart now has {items_count} item(s). What else would you like?"
        next_node = "build_cart"
    elif "order.confirm_cart" in intent_ids or "confirm_cart" in intent_ids:
        # Inspect last_oob for validation errors
        if last_oob and last_oob.get("last_validation_error") == "no_items":
            reply_text = "Your cart is empty. Add items before confirming."
            next_node = "build_cart"
        elif last_oob and last_oob.get("last_validation_error") == "invalid_quantity":
            reply_text = "One or more items have invalid quantities. Please correct them."
            next_node = "build_cart"
        else:
            reply_text = "Cart validated. I can calculate totals and review the order. Reply 'REVIEW ORDER' to continue."
            next_node = "order.review_order"
    elif "confirm_order" in intent_ids:
        reply_text = "Order confirmation received. (Next: implement ICE order create.)"
        next_node = "confirm_order_gate"
    elif "confirm_payment" in intent_ids:
        reply_text = "Payment confirmation received. (Next: implement ICE payment.)"
        next_node = "confirm_payment_gate"
    else:
        reply_text = "Tell me what you want, e.g. '2 apples' or '3 oranges'."
        next_node = "help"

    return _with_trace({
        "intent_ids": intent_ids,
        "next_node": next_node,
        "reply_text": reply_text,
        "render_type": "nlg",
        "template_id": "chat.stage.reply",
        "template_vars": {
            "stage": "chat",
            "sub_stage": "generic",
            "session_id": session_id,
            "bot_name": bot_meta.get("persona_name") or bot_meta.get("name") or None,
            "business_name": business_meta.get("name") or None,
            "is_returning": session_meta.get("is_returning"),
            "locale": (session_meta.get("locale") or payload.get("locale") or "en"),
            "timezone": session_meta.get("timezone"),
            "cta_labels": ["Play with a product", "Explore offers", "Help"],
        },
        "oob_ref": f"oob:{session_id}",
        "oob_summary": {"items_count": items_count, "oob_version": last_ver},
    })
