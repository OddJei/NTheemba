import pytest

from types import SimpleNamespace

from httpx import AsyncClient

from src.app import main as od_main


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class FakeDB:
    def __init__(self, rows):
        self._rows = rows

    async def execute(self, q):
        return FakeResult(self._rows)


def make_order(id, business_id, user_phone, status, total_amount=0, currency="ZMW", meta=None):
    return SimpleNamespace(
        id=id,
        business_id=business_id,
        user_phone=user_phone,
        status=status,
        total_amount=total_amount,
        currency=currency,
        meta=meta or {},
    )


@pytest.mark.asyncio
async def test_get_pending_orders_grouping(monkeypatch):
    # Create fake orders grouped by meta.subject
    o1 = make_order("o1", "b1", "0771", "pending_payment", total_amount=100, meta={"subject": "alice"})
    o2 = make_order("o2", "b1", "0772", "pending_payment", total_amount=200, meta={"subject": "alice"})
    o3 = make_order("o3", "b2", "0773", "pending_payment", total_amount=300, meta={"subject": "bob"})

    fake_db = FakeDB([o1, o2, o3])

    # Monkeypatch the dependency in main module
    monkeypatch.setattr(od_main, "get_db_session", lambda: fake_db)

    async with AsyncClient(app=od_main.app, base_url="http://test") as ac:
        r = await ac.get("/orders/pending")
    assert r.status_code == 200
    data = r.json()
    assert "alice" in data and "bob" in data
    assert len(data["alice"]) == 2
    assert len(data["bob"]) == 1


@pytest.mark.asyncio
async def test_get_pending_orders_filter_business(monkeypatch):
    o1 = make_order("o1", "b1", "0771", "pending_payment", total_amount=100, meta={"subject": "alice"})
    o2 = make_order("o2", "b2", "0772", "pending_payment", total_amount=200, meta={"subject": "alice"})

    fake_db = FakeDB([o1, o2])
    monkeypatch.setattr(od_main, "get_db_session", lambda: fake_db)

    async with AsyncClient(app=od_main.app, base_url="http://test") as ac:
        r = await ac.get("/orders/pending", params={"business_id": "b1"})
    assert r.status_code == 200
    data = r.json()
    # Only one subject group with one order
    total = sum(len(v) for v in data.values())
    assert total == 1
