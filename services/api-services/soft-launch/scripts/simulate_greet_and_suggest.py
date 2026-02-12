#!/usr/bin/env python3
"""Small E2E simulator for the `greet_and_suggest` intent.

Runs two scenarios:
- No ICE client (diagnostics for missing ICE)
- Mocked ICE client + fake resolver hydrate

Prints the returned `reply_text`, `recommendations`, and `context_snapshot`.
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
        return {"items": [{"id": "p1", "title": "Tomatoes", "price": 100}, {"id": "p2", "title": "Rice", "price": 200}, {"id": "p3", "title": "Onions", "price": 50}]}

    async def get_business_by_phone(self, phone: str, session_id: str | None = None):
        return {"name": "Mama's Market"}


async def _fake_resolve_required_blobs(store, session_id, required_blobs, ice_client=None, event_id=None):
    # Return a business and products blob as hydrate would
    return {
        "business": {"name": "Mama's Market"},
        "products": [
            {"id": "p1", "title": "Tomatoes", "price": 100},
            {"id": "p2", "title": "Rice", "price": 200},
            {"id": "p3", "title": "Onions", "price": 50},
        ],
    }


async def run():
    store = MockOOBStore()
    session_id = "sim-session-1"

    # Scenario 1: No ICE client
    print("--- Scenario 1: No ICE client ---")
    res1 = await greet_and_suggest(store=store, session_id=session_id, event_id="evt-1", ice_client=None)
    print(json.dumps({"reply_text": res1.get("reply_text"), "recommendations": res1.get("recommendations"), "context_snapshot": res1.get("context_snapshot")}, indent=2))

    # Scenario 2: Mocked ICE + fake resolver
    print("\n--- Scenario 2: Mocked ICE + fake resolver hydrate ---")
    # monkeypatch the resolver function inside the module so greet_and_suggest uses our fake
    import importlib

    mod = importlib.import_module("app.handlers.greet_and_suggest")
    mod.resolve_required_blobs = _fake_resolve_required_blobs

    ice = MockICEClient()
    res2 = await greet_and_suggest(store=store, session_id=session_id, event_id="evt-2", ice_client=ice)
    print(json.dumps({"reply_text": res2.get("reply_text"), "recommendations": res2.get("recommendations"), "context_snapshot": res2.get("context_snapshot")}, indent=2))


if __name__ == "__main__":
    asyncio.run(run())
