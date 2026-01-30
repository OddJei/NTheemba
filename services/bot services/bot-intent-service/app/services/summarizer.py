from typing import Any, Dict, List

from ..models.schemas import IntentRequest


def summarize_context(request: IntentRequest) -> str:
    """
    Condense rich session context into a dense string for the LLM prompt.
    Focuses on Cart, Session State, and recent history.
    """
    meta = request.enriched_meta or {}
    runtime_ctx = request.context or {}
    parts = []

    # 1. Session State
    # Look for 'session' or 'session_context' in meta
    session = meta.get("session") or {}
    # Use nested session_context if available (hydrated blob)
    session_ctx = meta.get("session_context") or {}
    
    current_node = session.get("current_node") or session_ctx.get("current_node")
    if current_node:
        parts.append(f"State: {current_node}")

    # 2. Cart / Order Draft
    # Expected in 'session_context' -> 'order_draft'
    order_draft = session_ctx.get("order_draft") or meta.get("order_draft")
    if order_draft and isinstance(order_draft, dict):
        items = order_draft.get("items", [])
        if items:
            item_summaries = []
            for item in items:
                # Dense format: "apple x2"
                name = item.get("name") or item.get("product_id") or "item"
                qty = item.get("quantity") or item.get("qty") or 1
                item_summaries.append(f"{name} x{qty}")
            
            cart_str = ", ".join(item_summaries)
            # Truncate if too long (arbitrary safe limit for the dense string)
            if len(cart_str) > 100:
                cart_str = cart_str[:97] + "..."
            parts.append(f"Cart: {len(items)} items ({cart_str})")

    # 2b. Runtime-provided OOB summary (custom-bot-service)
    # Expected shape: context.oob_summary.{items_count, last_node_executed, selected_category, selected_product}
    oob_summary = runtime_ctx.get("oob_summary") if isinstance(runtime_ctx, dict) else None
    if isinstance(oob_summary, dict):
        last_node = oob_summary.get("last_node_executed")
        if last_node and not any(p.startswith("State:") for p in parts):
            parts.append(f"State: {last_node}")
        items_count = oob_summary.get("items_count")
        if isinstance(items_count, int):
            parts.append(f"CartCount: {items_count}")

    # 3. User Profile (minimal)
    user = meta.get("user") or {}
    first_name = user.get("first_name")
    if first_name:
        parts.append(f"User: {first_name}")

    # 4. History (if available in meta)
    # Assuming 'previous_events' or similar list of dicts {text:..., sender:...}
    history = meta.get("previous_events") or []
    if history and isinstance(history, list):
        # Take last 2 turns max
        recent = history[-2:]
        hist_parts = []
        for evt in recent:
            sender = "User" if evt.get("from_user") else "Bot"
            text = evt.get("text") or evt.get("message") or "..."
            # Dense truncation
            if len(text) > 40:
                text = text[:37] + "..."
            hist_parts.append(f"{sender}: {text}")
        if hist_parts:
            parts.append("History: " + " | ".join(hist_parts))

    return "\n".join(parts)

