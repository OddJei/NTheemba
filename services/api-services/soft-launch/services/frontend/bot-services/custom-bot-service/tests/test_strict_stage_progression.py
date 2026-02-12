import os
import sys


def _add_app_path():
    here = os.path.dirname(__file__)
    app_parent = os.path.normpath(os.path.join(here, ".."))
    if app_parent not in sys.path:
        sys.path.insert(0, app_parent)


_add_app_path()

from app import runtime_engine as engine  # type: ignore


def test_strict_progression_includes_prereqs():
    resolved = {
        "intents": {
            "payment": [
                {"intent_id": "confirm_payment", "confidence": 0.9, "slots": {}}
            ]
        }
    }
    intents = engine._flatten_resolved_intents(resolved, "chat")
    queue = engine._build_stage_queue("chat", intents)
    assert queue == ["chat", "cart", "order", "payment"]


def test_backtracking_does_not_skip_forward():
    resolved = {
        "intents": {
            "chat": [
                {"intent_id": "help", "confidence": 0.8, "slots": {}}
            ]
        }
    }
    intents = engine._flatten_resolved_intents(resolved, "order")
    queue = engine._build_stage_queue("order", intents)
    assert queue == ["chat", "cart", "order"]


def test_flattened_intents_preserve_stage_hint():
    resolved = {
        "intents": {
            "cart": [
                {"intent_id": "add_item", "confidence": 0.9, "slots": {"quantity": 1}}
            ],
            "order": [
                {"intent_id": "order.review_order", "confidence": 0.7, "slots": {}}
            ],
        }
    }
    intents = engine._flatten_resolved_intents(resolved, "chat")
    stages = [engine._intent_stage_for(it, "chat") for it in intents]
    assert stages == ["cart", "order"]
