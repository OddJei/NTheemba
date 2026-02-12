#!/usr/bin/env python3
"""Build context via `greet_and_suggest`, pass it to the NLG renderer, and print the response text.

This script uses the same mocks as the simulator to produce a predictable context.
"""
import asyncio
import json
import os
import sys


def _add_import_path():
    root = os.getcwd()
    svc = os.path.join(root, "services", "frontend", "bot-services", "custom-bot-service")
    if svc not in sys.path:
        sys.path.insert(0, svc)


_add_import_path()

from app.handlers.greet_and_suggest import greet_and_suggest
from app import nlg_renderer


class MockOOBStore:
    def __init__(self):
        self._data = {}

    async def create_default_if_missing(self, session_id: str):
        oob = {
            "schema_version": "v1",
            "lock_version": 1,
            "last_event_id": None,
            "last_node_executed": None,
            "cart": {"items": [], "totals": {"subtotal": 0, "grand_total": 0}, "status": "building", "cart_version": 1},
            "meta": {},
        }
        self._data[session_id] = oob
        return oob, 1

    async def cas_update(self, session_id: str, updater, max_retries: int = 3):
        current = self._data.get(session_id, {})
        new = updater(current)
        if asyncio.iscoroutine(new):
            new = await new
        self._data[session_id] = new
        return new, 2


class MockICEClient:
    async def get_recommendations(self, session_id: str, count: int = 3):
        return {"items": [{"id": "p1", "title": "Tomatoes", "price": 100}, {"id": "p2", "title": "Rice", "price": 200}]}

    async def get_business_by_phone(self, phone: str, session_id: str | None = None):
        return {"name": "Mama's Market"}


async def _fake_resolve_required_blobs(store, session_id, required_blobs, ice_client=None, event_id=None):
    return {
        "business": {"name": "Mama's Market"},
        "products": [
            {"id": "p1", "title": "Tomatoes", "price": 100},
            {"id": "p2", "title": "Rice", "price": 200},
        ],
    }


async def main():
    store = MockOOBStore()
    session_id = "llm-session-1"

    # Monkeypatch resolver to return predictable blobs
    import importlib

    mod = importlib.import_module("app.handlers.greet_and_suggest")
    mod.resolve_required_blobs = _fake_resolve_required_blobs

    ice = MockICEClient()

    # Build context (greet_and_suggest returns context_snapshot)
    result = await greet_and_suggest(store=store, session_id=session_id, event_id="evt-llm", ice_client=ice)
    context_snapshot = result.get("context_snapshot") or {}

    # Prepare template_vars for render_reply — include stage, locale, business_name and missing_slots
    template_vars = {
        "stage": (context_snapshot.get("user_state") or {}).get("stage", "chat"),
        "locale": "en",
        "bot_name": (context_snapshot.get("user_state") or {}).get("bot_persona", "assistant"),
        "business_name": (context_snapshot.get("user_state") or {}).get("business_name"),
        "missing_slots": [],
        "fallback_text": "Sorry, I couldn't generate a reply right now.",
    }

    print("Context snapshot passed to LLM:")
    print(json.dumps(context_snapshot, indent=2))

    # Use only the direct prompt pattern: send the context snapshot and explicit
    # instruction directly to the LLM and print the raw output (no renderer path).
    try:
        prompt_parts = [
            "You are NTheemba, a friendly shopping assistant. Mix in light Bemba/Nyanja phrases (~10-20%).",
            "Context snapshot (JSON):",
            json.dumps(context_snapshot, indent=2),
            "Produce a concise reply that greets the user, mentions up to two suggested products from the context_snapshot only, and asks whether to add one to the cart."
        ]
        direct_prompt = "\n\n".join(prompt_parts)

        print('\nSending direct prompt to LLM (raw) ...')
        raw = await nlg_renderer._call_gemini(direct_prompt)
        print('\nRaw LLM output:')
        print(raw)
    except Exception as e:
        print('Direct LLM call failed:', e)


if __name__ == "__main__":
    asyncio.run(main())
