import os
import sys
import json
import urllib.request
import urllib.error

# Helper to read .env and get INTENT_GEMINI_API_KEY
def read_env_key(env_path):
    try:
        with open(env_path, 'r', encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if line.startswith('INTENT_GEMINI_API_KEY'):
                    _, val = line.split('=', 1)
                    return val.strip()
    except Exception:
        return None


# Add package parent so `app.handlers.resolve_multi_intent` imports correctly
pkg_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), 'services', 'frontend', 'bot-services', 'custom-bot-service'))
if pkg_parent not in sys.path:
    sys.path.insert(0, pkg_parent)

import importlib
resolver = importlib.import_module('app.handlers.resolve_multi_intent')


payload = {
    "text": "I want 2 bags of rice and 1 cooking oil",
    "meta": {"session": {"id": "sess-123", "is_returning": True, "locale": "en"}, "stage": "cart"},
}
cached_blobs = {"products": [{"id": "p1", "name": "Rice Large", "price": 15}, {"id": "p2", "name": "Cooking Oil 1L", "price": 8}], "cart_items": [{"product_id": "p1", "quantity": 1}]}

stage_value = resolver._extract_stage(payload, None)
context = resolver._build_context(payload, cached_blobs)
context["stage"] = stage_value
raw_text = resolver._extract_text(payload)

# Build strict payload same as resolver does
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
                    {"intent_id": "<string>", "confidence": "<float>", "slots": {}}
                ],
                "cart": [],
                "order": [],
                "payment": [],
                "delivery": [
                    {"intent_id": "<string>", "confidence": "<float>", "slots": {}}
                ],
                "closed": []
            },
            "diagnostics": {"missing": [], "notes": "<string>"}
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
                    {"intent_id": "<string>", "confidence": "<float>", "slots": {}}
                ],
                "cart": [],
                "order": [],
                "payment": [],
                "delivery": [
                    {"intent_id": "<string>", "confidence": "<float>", "slots": {}}
                ],
                "closed": []
            },
            "diagnostics": {"missing": [], "notes": "<string>"}
        }
    }

# Build request body using the REST `contents` format (single JSON part to avoid duplicate instruction)
body = {"contents": [{"parts": [{"text": json.dumps(strict_payload, ensure_ascii=False)}]}]}

# Determine API key: try env then .env file in the custom-bot-service
api_key = os.getenv('INTENT_GEMINI_API_KEY') or os.getenv('GEMINI_API_KEY')
if not api_key:
    env_path = os.path.join(os.path.dirname(__file__), 'services', 'frontend', 'bot-services', 'custom-bot-service', '.env')
    raw = read_env_key(env_path)
    if raw:
        api_key = raw.split(',')[0].strip()

if not api_key:
    print('ERROR: No API key found in environment or .env (INTENT_GEMINI_API_KEY)')
    sys.exit(1)

endpoint = os.getenv('INTENT_GEMINI_ENDPOINT', 'https://generativelanguage.googleapis.com/v1beta/models')
model = os.getenv('INTENT_GEMINI_MODEL', 'gemini-3-flash-preview')
if model.startswith('models/'):
    model = model[len('models/'):]
url = f"{endpoint}/{model}:generateContent"

data = json.dumps(body, ensure_ascii=False).encode('utf-8')
req = urllib.request.Request(url, data=data, method='POST')
req.add_header('Content-Type', 'application/json')
req.add_header('x-goog-api-key', api_key)

print('Posting strict payload to:', url)
print('\n--- REQUEST BODY ---')
print(json.dumps(body, indent=2, ensure_ascii=False))
try:
    # Increase urlopen timeout to allow the LLM more time to respond for larger prompts
    with urllib.request.urlopen(req, timeout=120) as resp:
        resp_text = resp.read().decode('utf-8')
        # Print to stdout for immediate feedback
        print('\n--- RESPONSE TEXT ---')
        print(resp_text)
        # Save raw response to a predictable file for further inspection
        out_path = os.path.join(os.path.dirname(__file__), 'strict_response_output.json')
        try:
            with open(out_path, 'w', encoding='utf-8') as ofh:
                ofh.write(resp_text)
            print(f"Saved response to: {out_path}")
        except Exception:
            pass
        try:
            parsed = json.loads(resp_text)
            print('\n--- PARSED JSON ---')
            print(json.dumps(parsed, indent=2, ensure_ascii=False))
        except Exception:
            pass
except urllib.error.HTTPError as he:
    try:
        err_text = he.read().decode('utf-8')
    except Exception:
        err_text = str(he)
    print('\n--- HTTP ERROR ---')
    print('Status:', he.code)
    print('Reason:', he.reason)
    print('Body:', err_text)
    sys.exit(2)
except Exception as e:
    print('Request failed:', e)
    sys.exit(2)
