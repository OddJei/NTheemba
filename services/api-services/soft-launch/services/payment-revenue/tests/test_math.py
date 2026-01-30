import os
import sys
import tempfile
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_DIR))

_db_file = Path(tempfile.gettempdir()) / f"payment_revenue_test_{uuid.uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_db_file.as_posix()}"

# Avoid external HTTP calls in tests by setting dummy URLs.
os.environ["MSME_BASE_URL"] = "http://127.0.0.1:9"
os.environ["ORDER_DELIVERY_BASE_URL"] = "http://127.0.0.1:9"
os.environ["AFFILIATE_ENGINE_BASE_URL"] = "http://127.0.0.1:9"

from src.app.main import app


AUTH_HEADERS = {"Authorization": "Bearer dummy-token", "X-Role": "admin"}


def test_payment_success_computes_and_persists_settlement(monkeypatch):
    # Patch dispatch to avoid network.
    from src.app import main as m

    async def _noop(*args, **kwargs):
        return None

    async def _fee(*args, **kwargs):
        return 500, "test"

    monkeypatch.setattr(m, "_dispatch_to_order_delivery", _noop)
    monkeypatch.setattr(m, "_dispatch_to_affiliate_engine", _noop)
    monkeypatch.setattr(m, "_dispatch_to_msme_engine_subscription", _noop)
    monkeypatch.setattr(m, "_get_fee_bps_for_business", _fee)

    with TestClient(app) as client:
        r = client.post(
            "/events/payment-success",
            headers={**AUTH_HEADERS, "X-Idempotency-Key": "p1"},
            json={
                "payment_id": "p1",
                "order_id": "o1",
                "business_id": "b1",
                "amount_minor": 10000,
                "currency": "ZMW",
            },
        )
        assert r.status_code in (200, 201)
        body = r.json()
        assert body["fee_bps"] == 500
        assert body["platform_fee_minor"] == 500
        assert body["msme_net_minor"] == 9500

        # Idempotent re-submit.
        r2 = client.post(
            "/events/payment-success",
            headers={**AUTH_HEADERS, "X-Idempotency-Key": "p1"},
            json={
                "payment_id": "p1",
                "order_id": "o1",
                "business_id": "b1",
                "amount_minor": 10000,
                "currency": "ZMW",
            },
        )
        assert r2.status_code in (200, 201)


def test_subscription_payment_success_dispatches_to_msme(monkeypatch):
    from src.app import main as m

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(m, "_dispatch_to_msme_engine_subscription", _noop)

    with TestClient(app) as client:
        r = client.post(
            "/events/subscription-payment-success",
            headers={**AUTH_HEADERS, "X-Idempotency-Key": "subp1"},
            json={
                "payment_id": "subp1",
                "business_id": "b_sub_1",
                "plan": "paid",
                "paid_until": "2026-07-11T00:00:00Z",
                "amount_minor": 70000,
                "currency": "ZMW",
            },
        )
        assert r.status_code in (200, 201)
        body = r.json()
        assert body["payment_id"] == "subp1"
        assert body["business_id"] == "b_sub_1"
        assert body["plan"] == "paid"

        # Idempotent replay
        r2 = client.post(
            "/events/subscription-payment-success",
            headers={**AUTH_HEADERS, "X-Idempotency-Key": "subp1"},
            json={
                "payment_id": "subp1",
                "business_id": "b_sub_1",
                "plan": "paid",
                "paid_until": "2026-07-11T00:00:00Z",
                "amount_minor": 70000,
                "currency": "ZMW",
            },
        )
        assert r2.status_code in (200, 201)


def test_payouts_endpoint_returns_ledger_rows(monkeypatch):
    from src.app import main as m

    async def _noop(*args, **kwargs):
        return None

    async def _fee(*args, **kwargs):
        return 500, "test"

    monkeypatch.setattr(m, "_dispatch_to_order_delivery", _noop)
    monkeypatch.setattr(m, "_dispatch_to_affiliate_engine", _noop)
    monkeypatch.setattr(m, "_get_fee_bps_for_business", _fee)
    monkeypatch.setattr(m, "get_affiliate_commission_share_of_platform_fee", lambda: 0.2)

    order_id = "o_payouts_1"
    payment_id = "p_payouts_1"
    business_id = "b_payouts_1"

    with TestClient(app) as client:
        r = client.post(
            "/events/payment-success",
            headers={**AUTH_HEADERS, "X-Idempotency-Key": payment_id},
            json={
                "payment_id": payment_id,
                "order_id": order_id,
                "business_id": business_id,
                "amount_minor": 10000,
                "currency": "ZMW",
            },
        )
        assert r.status_code in (200, 201)

        pr = client.get(f"/payouts/{order_id}", headers=AUTH_HEADERS)
        assert pr.status_code == 200
        rows = pr.json()
        assert isinstance(rows, list)
        assert len(rows) == 3

        by_type = {p["payee_type"]: p for p in rows}
        assert set(by_type.keys()) == {"msme", "affiliate", "platform"}

        assert by_type["msme"]["amount_minor"] == 9500
        assert by_type["affiliate"]["amount_minor"] == 100
        assert by_type["platform"]["amount_minor"] == 400

        assert by_type["msme"]["status"] == "dispatched"
        assert by_type["affiliate"]["status"] == "dispatched"
        assert by_type["platform"]["status"] == "dispatched"

        for p in rows:
            assert p["order_id"] == order_id
            assert p["payment_id"] == payment_id
            assert p["business_id"] == business_id
            assert p["currency"] == "ZMW"
