import os
import sys
import json

# Add package parent so `app.handlers.resolve_multi_intent` imports correctly
pkg_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), 'services', 'frontend', 'bot-services', 'custom-bot-service'))
if pkg_parent not in sys.path:
    sys.path.insert(0, pkg_parent)

import importlib
resolver = importlib.import_module('app.handlers.resolve_multi_intent')


payload = {
    "text": "I want 2 bags of rice and 1 cooking oil",
    "meta": {
        "session": {"id": "sess-123", "is_returning": True, "locale": "en"},
        "business": {"id": "biz-1", "name": "Corner Store"},
        "bot": {"persona_name": "ShopBot"},
        "stage": "cart",
    },
}

cached_blobs = {
    "products": [
        {"id": "p1", "name": "Rice Large", "price": 15},
        {"id": "p2", "name": "Cooking Oil 1L", "price": 8},
    ],
    "cart_items": [{"product_id": "p1", "quantity": 1}],
}

stage_value = resolver._extract_stage(payload, None)
context = resolver._build_context(payload, cached_blobs)
context["stage"] = stage_value
raw_text = resolver._extract_text(payload)

# Reconstruct the strict payload following the same logic in the resolver
strict_instruction = (
    "You are a strict JSON mapper for a commerce chatbot. DO NOT PRODUCE ANY PROSE, MARKDOWN, OR EXPLANATION — RETURN ONLY ONE VALID JSON OBJECT (no surrounding text). "
    "Only use intent IDs from the allowed canonical list provided below. If the user text does not match any, default to 'help' or 'cancel' under the chat stage. "
    "The product_snapshot and cart_items are context only — do not invent, remove, or modify them. Fill only the fields present in the provided `input.stages` for the selected stage. Preserve types. "
    "If a required field cannot be determined, set it to null and list it under `diagnostics.missing`."
)

allowed = {
    "chat": ["greet_and_suggest", "help", "cancel"],
    "cart": ["browse_catalogue", "add_item", "remove_item", "view_cart", "clear_cart", "inspect_item"],
    "order": ["order.confirm_cart", "order.review_order", "order.calculate_total", "order.check_stock", "confirm_order"],
    "payment": ["confirm_payment", "payment.verify_status"],
    "delivery": ["fulfillment.choose_method", "fulfillment.choose_location", "fulfillment.select_delivery_option"],
    "closed": [],
}

strict_input = {"user_text": raw_text}

ps = None
if isinstance(cached_blobs, dict):
    ps = cached_blobs.get("product_snapshot") or cached_blobs.get("products") or cached_blobs.get("available_products")

    if ps:
        strict_payload = {
            "instruction": strict_instruction,
            "allowed_intents": allowed,
            "product_snapshot": {"available_products": ps, "cart_items": cached_blobs.get("cart_items") or []},
            "input": strict_input,
            "output_format": {
                "session_id": "<string>",
                "stage": "<string>",
                "next_action": "<string>",
                "intents": {
                    "chat": [
                        {
                            "intent_id": "<string>",
                            "confidence": "<float>",
                            "slots": { }
                        }
                    ],
                    "cart": [],
                    "order": [],
                    "payment": [],
                    "delivery": [
                        {
                            "intent_id": "<string>",
                            "confidence": "<float>",
                            "slots": { }
                        }
                    ],
                    "closed": []
                },
                "diagnostics": {
                    "missing": [],
                    "notes": "<string>"
                }
            }
        }
    else:
        strict_payload = {
            "instruction": strict_instruction,
            "allowed_intents": allowed,
            "product_snapshot": {"available_products": [], "cart_items": []},
            "input": strict_input,
            "output_format": {
                "session_id": "<string>",
                "stage": "<string>",
                "next_action": "<string>",
                "intents": {
                    "chat": [
                        {
                            "intent_id": "<string>",
                            "confidence": "<float>",
                            "slots": { }
                        }
                    ],
                    "cart": [],
                    "order": [],
                    "payment": [],
                    "delivery": [
                        {
                            "intent_id": "<string>",
                            "confidence": "<float>",
                            "slots": { }
                        }
                    ],
                    "closed": []
                },
                "diagnostics": {
                    "missing": [],
                    "notes": "<string>"
                }
            }
        }

body = {"contents": [{"parts": [{"text": json.dumps(strict_payload, ensure_ascii=False)}]}]}

print("--- STRICT PAYLOAD ---")
print(json.dumps(strict_payload, indent=2, ensure_ascii=False))
print("\n--- FULL LLM BODY ---")
print(json.dumps(body, indent=2, ensure_ascii=False))
