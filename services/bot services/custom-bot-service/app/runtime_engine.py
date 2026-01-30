from __future__ import annotations

import logging
import time
import traceback
import asyncio
import uuid
from typing import Any
import re

from .intent_parser import Intent, parse_intents
from .intent_client import get_intents
from .oob_store import OOBStore
from .ice_client import IceClient
from .telemetry import emit_event, incr_metric
from .audit_client import emit_audit
from .session_cycle import start_cycle, complete_cycle, get_cycle
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

logger = logging.getLogger("custom_bot.engine")


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
    # Prefer the central intent-service when available (Phase C).
    intents: list[Intent] = []
    routing_hints = (payload.get("meta") or {}).get("routing_hints") if payload else None
    intent_required = bool(routing_hints and routing_hints.get("intent_required"))

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

    # attempt to call intent-service; if it fails or returns empty, fallback to local parser
    try:
        remote = await get_intents(event_id=event_id, session_id=session_id, raw_text=raw_text, context={"oob_summary": {}}, required=intent_required)
        if remote:
            intents = remote
        else:
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

    store = OOBStore()

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
            last_oob, last_ver = await _instrumented_call("confirm_cart", confirm_cart, store=store, session_id=session_id, event_id=event_id)
            try:
                if event_id:
                    await store.set_last_event(session_id, event_id)
            except Exception:
                pass
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
            # Strict confirm gate: runtime must pass raw_text; ICE client not configured in runtime yet.
            try:
                last_oob, last_ver = await _instrumented_call("confirm_order_gate", confirm_order_gate, store=store, session_id=session_id, event_id=event_id, raw_text=raw_text, ice_client=ice_client)
            except ValueError:
                return _with_trace({
                    "intent_ids": [i.id for i in intents],
                    "next_node": "confirm_order_gate",
                    "reply_text": "Order creation service not configured. I can only mark confirmation locally.",
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"items_count": (last_oob.get("cart") or {}).get("items") and len((last_oob.get("cart") or {}).get("items") or []) if last_oob else 0, "oob_version": last_ver},
                })
            except Exception:
                return _with_trace({
                    "intent_ids": [i.id for i in intents],
                    "next_node": "confirm_order_gate",
                    "reply_text": "Failed to create order. Try again later.",
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"items_count": (last_oob.get("cart") or {}).get("items") and len((last_oob.get("cart") or {}).get("items") or []) if last_oob else 0, "oob_version": last_ver},
                })
        elif intent.id in ("confirm_payment", "order.confirm_payment"):
            try:
                last_oob, last_ver = await _instrumented_call("confirm_payment_gate", confirm_payment_gate, store=store, session_id=session_id, event_id=event_id, raw_text=raw_text, ice_client=ice_client)
            except ValueError:
                return {
                    "intent_ids": [i.id for i in intents],
                    "next_node": "confirm_payment_gate",
                    "reply_text": "Payment service not configured. I can only mark confirmation locally.",
                    "oob_ref": f"oob:{session_id}",
                    "oob_summary": {"items_count": (last_oob.get("cart") or {}).get("items") and len((last_oob.get("cart") or {}).get("items") or []) if last_oob else 0, "oob_version": last_ver},
                }
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
            res = await _instrumented_call("greet_and_suggest", greet_and_suggest, store=store, session_id=session_id, event_id=event_id, ice_client=ice_client)
            # `res` contains keys: oob, oob_ver, reply_text
            return _with_trace({
                "intent_ids": [i.id for i in intents],
                "next_node": "greet_and_suggest",
                "reply_text": res.get("reply_text") or "Hi",
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
        "oob_ref": f"oob:{session_id}",
        "oob_summary": {"items_count": items_count, "oob_version": last_ver},
    })
