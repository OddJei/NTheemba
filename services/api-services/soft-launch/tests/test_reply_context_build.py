import asyncio
import json
import sys
import os


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
        return {"items": [{"id": "p1", "title": "Tomatoes", "price": 100}]}

    async def get_business_by_phone(self, phone: str, session_id: str | None = None):
        return {"name": "Mama's Market"}


async def _fake_resolve_required_blobs(store, session_id, required_blobs, ice_client=None, event_id=None):
    return {
        "business": {"name": "Mama's Market"},
        "products": [{"id": "p1", "title": "Tomatoes", "price": 100}],
    }


def test_build_context_and_print():
    """Construct the reply context via `greet_and_suggest` and print it.

    Run pytest with `-s` to see the printed output in the terminal.
    """
    store = MockOOBStore()
    session_id = "test-session-1"

    # Monkeypatch resolver inside the module so hydrate returns predictable blobs
    import importlib

    mod = importlib.import_module("app.handlers.greet_and_suggest")
    mod.resolve_required_blobs = _fake_resolve_required_blobs

    ice = MockICEClient()

    result = asyncio.run(greet_and_suggest(store=store, session_id=session_id, event_id="evt-test", ice_client=ice))

    # Print the context_snapshot to terminal for inspection
    print(json.dumps(result.get("context_snapshot"), indent=2))

    assert "context_snapshot" in result and isinstance(result["context_snapshot"], dict)
