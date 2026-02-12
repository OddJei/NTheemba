# response_validator.py
"""
Validator for strict LLM response structure.
Validates top-level keys, stage membership, allowed intent IDs, confidence range, slots type, and diagnostics.
Returns (is_valid, errors, normalized_payload).
"""
from typing import Any, Dict, List, Tuple

ALLOWED_STAGES = ["chat", "cart", "order", "payment", "delivery", "closed"]

# Example mapping; update as needed from runtime_engine.py
ALLOWED_INTENTS = {
    "chat": ["ask_question", "clarify", "greet"],
    "cart": ["add_to_cart", "remove_from_cart", "view_cart"],
    "order": ["create_order", "cancel_order", "view_order"],
    "payment": ["initiate_payment", "confirm_payment", "view_payment"],
    "delivery": ["track_delivery", "confirm_delivery", "view_delivery"],
    "closed": ["close_session", "feedback", "goodbye"],
}

REQUIRED_TOP_LEVEL = ["session_id", "stage", "next_action", "intents", "diagnostics"]


def validate_response(payload: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
    errors = []
    normalized = dict(payload)

    # Top-level keys
    for key in REQUIRED_TOP_LEVEL:
        if key not in payload:
            errors.append(f"missing: {key}")

    # session_id
    if "session_id" in payload and not (isinstance(payload["session_id"], str) or payload["session_id"] is None):
        errors.append("session_id must be string or null")

    # stage
    stage = payload.get("stage")
    if stage not in ALLOWED_STAGES:
        errors.append(f"stage must be one of {ALLOWED_STAGES}, got {stage}")

    # next_action
    if "next_action" in payload and not (isinstance(payload["next_action"], str) or payload["next_action"] is None):
        errors.append("next_action must be string or null")

    # intents
    intents = payload.get("intents", {})
    if not isinstance(intents, dict):
        errors.append("intents must be an object grouped by stage")
    else:
        for stage_name, intent_list in intents.items():
            if stage_name not in ALLOWED_STAGES:
                errors.append(f"intents: invalid stage {stage_name}")
            if not isinstance(intent_list, list):
                errors.append(f"intents[{stage_name}] must be a list")
                continue
            allowed_ids = ALLOWED_INTENTS.get(stage_name, [])
            for idx, intent in enumerate(intent_list):
                if not isinstance(intent, dict):
                    errors.append(f"intents[{stage_name}][{idx}] must be an object")
                    continue
                intent_id = intent.get("id") or intent.get("intent_id")
                if intent_id not in allowed_ids:
                    errors.append(
                        f"intents[{stage_name}][{idx}].id must be one of {allowed_ids}, got {intent_id}"
                    )
                confidence = intent.get("confidence")
                if not (isinstance(confidence, float) or isinstance(confidence, int)) or not (0.0 <= confidence <= 1.0):
                    errors.append(f"intents[{stage_name}][{idx}].confidence must be float 0..1")
                slots = intent.get("slots")
                if not isinstance(slots, dict):
                    errors.append(f"intents[{stage_name}][{idx}].slots must be object")

    # diagnostics
    diagnostics = payload.get("diagnostics", {})
    if not isinstance(diagnostics, dict):
        errors.append("diagnostics must be object")
    else:
        if "missing" in diagnostics and not isinstance(diagnostics["missing"], list):
            errors.append("diagnostics.missing must be list")
        if "notes" in diagnostics and not isinstance(diagnostics["notes"], list):
            errors.append("diagnostics.notes must be list")

    is_valid = len(errors) == 0
    normalized["diagnostics"] = diagnostics if isinstance(diagnostics, dict) else {}
    if not is_valid:
        normalized.setdefault("diagnostics", {}).setdefault("missing", []).extend(errors)
    return is_valid, errors, normalized
