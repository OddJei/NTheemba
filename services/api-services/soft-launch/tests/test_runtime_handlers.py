import asyncio
import sys
import os
import pytest


def _add_import_path():
    root = os.getcwd()
    svc = os.path.join(root, "services", "frontend", "bot-services", "custom-bot-service")
    if svc not in sys.path:
        sys.path.insert(0, svc)


_add_import_path()

from app import runtime_engine as re
from app.handlers.clear_cart import clear_cart


class FakeOOBStore:
    def __init__(self):
        self._data = {}
        self._versions = {}

    async def get_oob(self, session_id: str):
        o = self._data.get(session_id)
        if o is None:
            # mirror DEFAULT_OOB shape minimally
            o = {"cart": {"items": [], "totals": {}, "status": "building", "cart_version": 1}, "meta": {}}
            self._data[session_id] = o
            self._versions[session_id] = 1
        return self._data[session_id], self._versions.get(session_id, 1)

    async def cas_update(self, session_id: str, updater, max_retries: int = 3):
        current = self._data.get(session_id, {"cart": {"items": [], "totals": {}, "status": "building", "cart_version": 1}, "meta": {}})
        new = updater(current)
        if asyncio.iscoroutine(new):
            new = await new
        self._data[session_id] = new
        self._versions[session_id] = self._versions.get(session_id, 1) + 1
        return new, self._versions[session_id]


class FakeIce:
    def __init__(self, products=None, categories=None, slots=None):
        self.enabled = True
        self._products = products or [
            {"id": f"p{i}", "name": f"Prod{i}", "price": 10 + i, "category_id": "c1" if i % 2 == 0 else "c2"}
            for i in range(1, 8)
        ]
        self._categories = categories or [{"id": "c1", "name": "Cat1"}, {"id": "c2", "name": "Cat2"}]
        self._slots = slots or {"c1": ["s1"], "c2": ["s2"]}

    async def hydrate(self, *, session_id: str, required_blobs: list[str], event_id: str | None = None):
        # return blobs as expected by runtime_engine
        resp = {}
        # pick the key requested
        key = None
        for k in required_blobs:
            if k.startswith("products"):
                key = k
                break
        if key:
            resp[key] = self._products
        resp["products"] = self._products
        resp["categories"] = self._categories
        resp["category_slots"] = self._slots
        return resp


@pytest.mark.asyncio
async def test_fetch_and_group_products_groups_by_category_when_many():
    store = FakeOOBStore()
    ice = FakeIce()
    grouped, cats, slots, diag = await re.fetch_and_group_products(store=store, session_id="s1", category_id=None, ice_client=ice, event_id="e1")
    # When >5 products, grouped should be by category
    assert isinstance(grouped, list) and len(grouped) >= 1
    # each product in groups must have id,name,price
    for g in grouped:
        assert "products" in g
        for p in g["products"]:
            assert set(p.keys()) >= {"id", "name", "price"}


def test_build_catalogue_context_includes_expected_keys():
    snapshot = {"user_text": "I want bread", "diagnostics": {}, "user_state": {}}
    grouped = [{"category_id": "c1", "category_name": "Cat1", "products": [{"id": "p1", "name": "X", "price": 10}]}]
    cats = [{"id": "c1", "name": "Cat1"}]
    slots = {"c1": ["s1"]}
    store_oob = {"cart": {"items": [{"id": "p1", "name": "X", "price": 10}]}}
    ctx = re.build_catalogue_context(snapshot=snapshot, grouped_products=grouped, categories=cats, slots=slots, store_oob=store_oob)
    assert ctx.get("user_text") == "I want bread"
    assert "groups" in ctx and ctx["groups"] == grouped
    assert "categories" in ctx and ctx["categories"] == cats
    assert "category_slots" in ctx and ctx["category_slots"] == slots
    assert "cart_items" in ctx


@pytest.mark.asyncio
async def test_execute_multi_intent_mapper_add_and_view():
    # prepare a fake store compatible with handlers.add_item and handlers.cart_view
    store = FakeOOBStore()
    session_id = "sess-1"

    mapper = {"intents": [{"id": "add_item", "slots": {"product_name": "Bread", "quantity": 2}}, {"id": "view_cart"}]}

    results = await re.execute_multi_intent_mapper(store=store, session_id=session_id, mapper=mapper, event_id="evt", ice_client=None)
    assert isinstance(results, list) and len(results) == 2
    assert results[0]["intent_id"] in ("add_item",) and results[0]["status"] == "ok"
    assert results[1]["intent_id"] in ("view_cart",) and results[1]["status"] == "ok"
    # the view_cart summary should reflect the added item
    summary = results[1].get("summary")
    assert summary and summary.get("items_count") == 1


@pytest.mark.asyncio
async def test_clear_cart_resets_cart():
    store = FakeOOBStore()
    session_id = "sess-clear"
    # pre-populate cart
    await store.cas_update(session_id, lambda o: {**o, "cart": {"items": [{"product_name": "X", "quantity": 1}], "totals": {}, "status": "building"}})
    # monkeypatch the OOBStore constructor used inside the handler to return our fake store
    import importlib

    mod = importlib.import_module("app.handlers.clear_cart")
    mod.OOBStore = lambda *a, **k: store

    oob, ver = await clear_cart(store=store, session_id=session_id, event_id="evt-1")
    assert oob.get("cart") and oob["cart"].get("items") == []
