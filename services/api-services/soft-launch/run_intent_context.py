import os
import sys
import json

# Add package parent so `app.handlers.resolve_multi_intent` imports correctly
pkg_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), 'services', 'frontend', 'bot-services', 'custom-bot-service'))
if pkg_parent not in sys.path:
    sys.path.insert(0, pkg_parent)

import importlib
resolver = importlib.import_module('app.handlers.resolve_multi_intent')

# Sample payload and cached blobs
payload = {
    "text": "I'd like to buy 2 bags of rice and a bottle of cooking oil",
    "meta": {
        "session": {"id": "sess-123", "is_returning": True, "locale": "en"},
        "business": {"id": "biz-1", "name": "Corner Store"},
        "bot": {"persona_name": "ShopBot"},
        "stage": "cart"
    }
}

cached_blobs = {
    "products": [
        {"id": "p1", "name": "Rice Large", "price": 15},
        {"id": "p2", "name": "Cooking Oil 1L", "price": 8}
    ],
    "recommendations": [{"id": "p3", "name": "Beans", "price": 5}],
}

context = resolver._build_context(payload, cached_blobs)
compact = resolver._compact_json(context, max_chars=1000)
stage = resolver._extract_stage(payload, None)
raw_text = resolver._extract_text(payload)
ids = resolver._normalize_canonical_ids(None)
ids_text = ", ".join(ids)

instruction = (
    "You are a multi-intent extraction service for a commerce chat bot. "
    "RETURN ONLY ONE JSON OBJECT with NO MARKDOWN and NO extra text. "
    "The object MUST contain: intents (non-empty array) and next_action. "
    "Each intent MUST be: {id: string, confidence: number 0..1, slots: object, hints?: object}. "
    "next_action must be one of: reply|outbound|none. "
    f"Use canonical ids: {ids_text}. "
    "If stage is chat and user intent is unclear, return greet_and_suggest."
)

parts = [
    {"text": instruction},
    {"text": f"Context:\n{compact}"},
    {"text": f"User: {raw_text}"},
]

print("--- BUILT CONTEXT (dict) ---")
print(json.dumps(context, indent=2))
print("\n--- COMPACT CONTEXT ---")
print(compact)
print("\n--- INSTRUCTION ---")
print(instruction)
print("\n--- PROMPT PARTS ---")
print(json.dumps(parts, indent=2))
