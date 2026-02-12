import os
import sys
import json
import asyncio

pkg_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if pkg_parent not in sys.path:
    sys.path.insert(0, pkg_parent)

import importlib
resolver = importlib.import_module('app.handlers.resolve_multi_intent')


CAPTURED = []


class DummyResp:
    def raise_for_status(self):
        return None

    def json(self):
        return {}


class DummyClient:
    def __init__(self, *args, **kwargs):
        self.captured = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, headers=None, json=None):
        # capture payload for assertions
        entry = {"url": url, "headers": headers, "json": json}
        CAPTURED.append(entry)
        return DummyResp()


def test_resolve_multi_intent_sends_expected_context(monkeypatch):
    # ensure resolver will attempt to call Gemini (module-level constant set at import)
    resolver.INTENT_GEMINI_API_KEY = 'test-key'

    # patch httpx.AsyncClient to capture request
    import httpx

    monkeypatch.setattr(httpx, 'AsyncClient', DummyClient)

    payload = {
        "text": "hey how are you do you have bread give me 3 i will come pick up in the morning!",
        "meta": {
            "session": {"id": "abc123", "is_returning": True, "locale": "en"},
            "business": {"id": "biz-1", "name": "Corner Store"},
            "bot": {"persona_name": "ShopBot"},
        },
    }

    cached_blobs = {
        "product_snapshot": [
            {"product_id": "bread001", "name": "Bread", "price": 2.5},
            {"product_id": "milk001", "name": "Milk", "price": 1.8},
        ],
        "cart_items": [{"product_id": "bread001", "name": "Bread", "quantity": 3, "price": 2.5}],
    }

    # call resolver
    asyncio.run(resolver.resolve_multi_intent(payload=payload, cached_blobs=cached_blobs, stage=None))

    assert CAPTURED, "Expected resolver to call the LLM endpoint and capture the request"
    sent = CAPTURED[0]
    body = sent.get('json') or {}
    # inspect prompt parts
    prompt = (body.get('prompt') or {}).get('messages') or []
    assert prompt, "No prompt messages found in request body"
    parts = prompt[0].get('content', {}).get('parts') or []

    # Build expected compacted context using resolver helpers
    expected_ctx = resolver._build_context(payload, cached_blobs)
    # resolve_multi_intent sets stage after building context
    expected_ctx["stage"] = resolver._extract_stage(payload, None)
    expected_compact = resolver._compact_json(expected_ctx)

    # find the Context part and compare exact compact JSON
    ctx_text = None
    for p in parts:
        t = p.get('text') if isinstance(p, dict) else None
        if t and t.startswith('Context:'):
            ctx_text = t[len('Context:\n'):]
            break

    assert ctx_text is not None, "Context part not found in prompt parts"
    assert ctx_text == expected_compact, f"Context mismatch:\nexpected:{expected_compact}\nactual:{ctx_text}"

    # ensure user text is present in User part
    user_part = None
    for p in parts:
        t = p.get('text') if isinstance(p, dict) else None
        if t and t.startswith('User:'):
            user_part = t[len('User: '):]
            break

    assert user_part is not None and 'give me 3' in user_part
