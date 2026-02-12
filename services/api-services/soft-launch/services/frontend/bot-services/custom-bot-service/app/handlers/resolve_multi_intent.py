from __future__ import annotations

import json
import os
from typing import Any

import httpx


INTENT_GEMINI_ENDPOINT = os.getenv(
    "INTENT_GEMINI_ENDPOINT",
    "https://generativelanguage.googleapis.com/v1beta/models",
)
INTENT_GEMINI_MODEL = os.getenv("INTENT_GEMINI_MODEL", "gemini-1.5-pro")
INTENT_GEMINI_API_KEY = os.getenv("INTENT_GEMINI_API_KEY") or os.getenv("gemini_key")
INTENT_USE_STRICT_MAPPER = os.getenv("INTENT_USE_STRICT_MAPPER", "False") == "True"


def _compact_json(obj: Any, max_chars: int = 1200) -> str:
    try:
        text = json.dumps(obj, ensure_ascii=True, default=str)
    except Exception:
        text = str(obj)
    if len(text) > max_chars:
        return text[: max_chars - 3] + "..."
    return text


def _extract_text(payload: dict[str, Any]) -> str:
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
            return cur.strip()
    return ""


def _build_context(payload: dict[str, Any], cached_blobs: dict[str, Any] | None) -> dict[str, Any]:
    cached = cached_blobs if isinstance(cached_blobs, dict) else {}
    meta = payload.get("meta") if isinstance(payload, dict) else None
    meta = meta if isinstance(meta, dict) else {}

    session = meta.get("session") if isinstance(meta, dict) else None
    business = meta.get("business") if isinstance(meta, dict) else None
    bot = meta.get("bot") if isinstance(meta, dict) else None

    ctx = {
        "stage": (meta.get("stage") if isinstance(meta, dict) else None) or payload.get("stage"),
        "session": session if isinstance(session, dict) else {},
        "business": business if isinstance(business, dict) else {},
        "bot": bot if isinstance(bot, dict) else {},
        "cached_blobs": cached,
    }

    # Reduce cached blobs to top-level signal fields if present.
    for key in ("product_snapshot", "products", "catalog", "suggestions", "recommendations"):
        if key in cached and isinstance(cached[key], list):
            ctx["product_snapshot"] = cached[key][:5]
            break

    return ctx


def _extract_json(raw: dict[str, Any]) -> dict[str, Any] | None:
    try:
        candidates = raw.get("candidates") or []
        if candidates:
            text = candidates[0]["content"]["parts"][0]["text"]
        else:
            text = json.dumps(raw, default=str)
    except Exception:
        text = None

    if not text:
        return None

    start = None
    for i, ch in enumerate(text):
        if ch == "{":
            start = i
            break
    if start is None:
        return None

    try:
        obj = json.loads(text[start:])
        if isinstance(obj, dict):
            return obj
    except Exception:
        return None

    return None


def _sanitize_model_output(parsed: dict[str, Any], original_product_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Sanitize model output to enforce read-only constraints and record diagnostics.

    - Reset any modifications to `product_snapshot.cart_items` back to the original.
    - Remove any `cart_items` the model injected under `stages.*`.
    - Remove `product_snapshot` from the entire response (recursively).
    - Append brief notes into `diagnostics.notes` describing changes.
    """
    notes: list[str] = []

    def remove_product_snapshot(obj: Any) -> Any:
        if isinstance(obj, dict):
            # Remove product_snapshot key
            if "product_snapshot" in obj:
                del obj["product_snapshot"]
                notes.append("removed product_snapshot from response")
            # Recurse into nested dicts and lists
            for key, value in obj.items():
                obj[key] = remove_product_snapshot(value)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                obj[i] = remove_product_snapshot(item)
        return obj

    parsed = remove_product_snapshot(parsed)

    # Reset mutated product_snapshot.cart_items if they differ from original
    if isinstance(original_product_snapshot, dict):
        orig_cart = original_product_snapshot.get("cart_items")
        if orig_cart is not None:
            ps = parsed.get("product_snapshot")
            if isinstance(ps, dict):
                parsed_cart = ps.get("cart_items")
                if parsed_cart is not None and parsed_cart != orig_cart:
                    ps["cart_items"] = orig_cart
                    notes.append("product_snapshot.cart_items modified by model; reset to original")

    # Remove any invented cart_items under stages
    stages = parsed.get("stages")
    if isinstance(stages, dict):
        removed: list[str] = []
        for sname, sdata in list(stages.items()):
            if isinstance(sdata, dict) and "cart_items" in sdata:
                try:
                    del sdata["cart_items"]
                except Exception:
                    pass
                removed.append(sname)
        if removed:
            notes.append(f"removed invented stages.cart_items for stages: {', '.join(removed)}")

    # Ensure diagnostics exists and append notes
    diag = parsed.get("diagnostics")
    if not isinstance(diag, dict):
        diag = {"missing": [], "notes": None}
        parsed["diagnostics"] = diag

    existing = diag.get("notes")
    if notes:
        combined = "; ".join([str(x) for x in notes])
        if existing:
            diag["notes"] = f"{existing}; {combined}"
        else:
            diag["notes"] = combined

    return parsed


def _extract_stage(payload: dict[str, Any], stage: str | None) -> str:
    if isinstance(stage, str) and stage.strip():
        return stage.strip().lower()
    try:
        meta = payload.get("meta") if isinstance(payload, dict) else None
        if isinstance(meta, dict) and isinstance(meta.get("stage"), str):
            return meta["stage"].strip().lower()
    except Exception:
        pass
    if isinstance(payload.get("stage"), str):
        return str(payload.get("stage")).strip().lower()
    return "chat"


def _normalize_canonical_ids(canonical_ids: list[str] | None) -> list[str]:
    if not canonical_ids:
        return [
            "greet_and_suggest",
            "add_item",
            "remove_item",
            "view_cart",
            "clear_cart",
            "help",
            "cancel",
            "confirm_order",
            "confirm_payment",
            "browse_catalogue",
        ]
    return [str(x) for x in canonical_ids if str(x).strip()]


async def resolve_multi_intent(
    *,
    payload: dict[str, Any],
    cached_blobs: dict[str, Any] | None = None,
    stage: str | None = None,
    canonical_ids: list[str] | None = None,
    model: str | None = None,
    max_output_tokens: int = 120,
    use_strict_mapper: bool | None = None,
    ) -> dict[str, Any]:
    """Call Gemini to produce a multi-intent JSONB response.

    Uses the payload plus cached blobs to reduce ambiguity.
    """
    if not INTENT_GEMINI_API_KEY:
        return {
            "intents": [{"id": "greet_and_suggest", "confidence": 0.4, "slots": {}}],
            "next_action": "reply",
            "diagnostics": {"error": "missing_api_key"},
        }

    # determine strict mapper usage: explicit arg -> env var -> default False
    strict = use_strict_mapper if use_strict_mapper is not None else INTENT_USE_STRICT_MAPPER

    stage_value = _extract_stage(payload, stage)
    context = _build_context(payload, cached_blobs)
    context["stage"] = stage_value
    raw_text = _extract_text(payload)

    ids = _normalize_canonical_ids(canonical_ids)

    if strict:
        # Build the strict JSON mapper payload per user's instruction contract.
        strict_instruction = (
            "You are a strict JSON mapper for a commerce chatbot. DO NOT PRODUCE ANY PROSE, MARKDOWN, OR EXPLANATION — RETURN ONLY ONE VALID JSON OBJECT (no surrounding text). RETURN ONLY the object that matches the `output_format` structure provided below (no extra fields, no wrappers). Always return the same predictable structure exactly as the `output_format` schema: `session_id`, `stage`, `next_action`, `intents` (with keys chat, cart, order, payment, delivery, closed), and `diagnostics`. Use only intent IDs from the allowed canonical lists provided. If the user text does not match any intent, include `help` or `cancel` under `intents.chat`. The `product_snapshot` and `cart_items` in the prompt are read-only context: do not invent, remove, or modify them. Preserve types: return strings for string fields, floats for confidence, arrays for lists, objects for maps, and null for unknown required values. For any required field you cannot determine, set it to null and enumerate its path under `diagnostics.missing` (array). Each intent entry must include `intent_id`, `confidence` (0–1 float), and `slots` (object, empty if none). Group intents by stage and return empty arrays when no intents for a stage."
        )

        allowed = {
            "chat": [
                "greet_and_suggest",
                "help",
                "cancel",
                "browse_catalogue",
                "view_cart",
                "add_item",
                "remove_item",
                "clear_cart",
            ],
            "cart": [
                "browse_catalogue",
                "add_item",
                "remove_item",
                "view_cart",
                "clear_cart",
                "inspect_item",
            ],
            "order": [
                "order.confirm_cart",
                "order.review_order",
                "order.calculate_total",
                "order.check_stock",
                "confirm_order",
            ],
            "payment": [
                "confirm_payment",
                "payment.verify_status",
            ],
            "delivery": [
                "fulfillment.choose_method",
                "fulfillment.choose_location",
                "fulfillment.select_delivery_option",
            ],
            "closed": [],
        }

        # Build the exact strict payload structure requested by the user. Use the current session id and user text.
        strict_payload = {
            "instruction": strict_instruction,
            "allowed_intents": allowed,
            "product_snapshot": {
                "available_products": [
                    {"product_id": "bread001", "name": "Bread", "price": 2.50},
                    {"product_id": "milk001", "name": "Milk", "price": 1.80},
                    {"product_id": "eggs001", "name": "Eggs (dozen)", "price": 3.20},
                ],
                "cart_items": [
                    {"product_id": "bread001", "name": "Bread", "quantity": 3, "price": 2.50}
                ],
                "orders": [
                    {"id": "order123", "total_price": 15.0, "confirmed": True},
                    {"id": "order456", "total_price": 8.5, "confirmed": False},
                ],
            },
            "input": {"user_text": raw_text},
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

        # Avoid repeating the instruction twice: send the full strict_payload JSON as the single part.
        # Use the REST `contents` request shape so the request body matches other tooling.
        parts = [
            {"text": json.dumps(strict_payload, ensure_ascii=False)},
        ]

        body = {
            "contents": [
                {"parts": parts},
            ]
        }

    else:
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
            {"text": f"Context:\n{_compact_json(context)}"},
            {"text": f"User: {raw_text}"},
        ]

        body = {
            "maxOutputTokens": int(max_output_tokens),
            "prompt": {"messages": [{"role": "user", "content": {"parts": parts}}]},
        }

    model = model or INTENT_GEMINI_MODEL
    if model.startswith("models/"):
        model = model[len("models/"):]

    url = f"{INTENT_GEMINI_ENDPOINT}/{model}:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": INTENT_GEMINI_API_KEY}

    # Use a longer timeout for longer prompts/responses
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

    parsed = _extract_json(data)
    if parsed:
        # If we used strict mode, validate and sanitize parsed JSON to enforce read-only constraints
        if strict:
            try:
                # Validate response structure
                from ..validators.response_validator import validate_response
                is_valid, errors, normalized = validate_response(parsed)
                parsed = normalized
                if not is_valid:
                    diag = parsed.get("diagnostics")
                    if not isinstance(diag, dict):
                        parsed["diagnostics"] = {"missing": [], "notes": "validator_failed"}
                    else:
                        notes = diag.get("notes") or ""
                        diag["notes"] = f"{notes}; validator_failed" if notes else "validator_failed"
                # Sanitize after validation
                parsed = _sanitize_model_output(parsed, strict_payload.get("product_snapshot"))
            except Exception:
                # If validator or sanitizer fails, leave parsed as-is but record a diagnostic
                diag = parsed.get("diagnostics")
                if not isinstance(diag, dict):
                    parsed["diagnostics"] = {"missing": [], "notes": "validator_or_sanitizer_failed"}
                else:
                    notes = diag.get("notes") or ""
                    diag["notes"] = f"{notes}; validator_or_sanitizer_failed" if notes else "validator_or_sanitizer_failed"
        return parsed

    return {
        "intents": [{"id": "greet_and_suggest", "confidence": 0.4, "slots": {}}],
        "next_action": "reply",
        "diagnostics": {"error": "parse_failed"},
    }
