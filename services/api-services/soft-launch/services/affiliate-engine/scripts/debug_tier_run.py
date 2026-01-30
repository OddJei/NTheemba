"""Reproduce failing test scenario and call admin debug endpoint.

This script is runnable from the repo root or any cwd — it ensures the
`services/affiliate-engine` package root is on sys.path so `src` imports work.
"""
import os
import sys
import uuid
from pathlib import Path

# Ensure affiliate-engine package root is on sys.path so `import src...` works
THIS = Path(__file__).resolve()
# affiliate-engine root is two levels up from this script (scripts/ -> affiliate-engine/)
AFF_ROOT = THIS.parent.parent
sys.path.insert(0, str(AFF_ROOT))

from fastapi.testclient import TestClient
from src.app.main import app
from src.app.db import Base, engine

client = TestClient(app)


def setup_app():
    # Run FastAPI startup handlers and ensure DB schema exists (like tests do)
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(app.router.startup())
        # Create DB tables
        loop.run_until_complete(engine.begin())
        # Use run_sync to create tables
        async def _create():
            await engine.run_sync(Base.metadata.create_all)

        loop.run_until_complete(_create())
    finally:
        loop.close()


setup_app()

os.environ["AFFILIATE_TIER_GOLD_GMV_MIN_ZMW"] = "1"
os.environ["AFFILIATE_TIER_GOLD_BUYERS_MIN"] = "1"
os.environ["AFFILIATE_TIER_GOLD_REFERRALS_MIN"] = "0"
os.environ["AFFILIATE_TIER_GOLD_CUSTOMERS_MIN"] = "1"
os.environ["AFFILIATE_OP_MIN_CLICKS"] = "1"
os.environ["AFFILIATE_OP_MIN_PAID_ATTRIBUTIONS"] = "1"
os.environ["AFFILIATE_OP_MIN_UNIQUE_BUYERS"] = "1"
os.environ["AFFILIATE_OP_MIN_SALES_VOLUME"] = "1"

headers_admin = {"X-Admin-Key": "test-admin"}

def _uuid():
    return str(uuid.uuid4())

# Create affiliates A2 and B2
r = client.post("/affiliates", headers={"X-Idempotency-Key": "create-A2", "X-Correlation-Id": "c-A2"}, json={"name": "A2", "phone": "+260900000011"})
assert r.status_code == 200
A = r.json()["id"]

r = client.post("/affiliates", headers={"X-Idempotency-Key": "create-B2", "X-Correlation-Id": "c-B2"}, json={"name": "B2", "phone": "+260900000021"})
assert r.status_code == 200
B = r.json()["id"]

# Create links
r = client.post(f"/affiliates/{A}/links", headers={"X-Idempotency-Key": "link-A2", "X-Correlation-Id": "c-linkA"}, json={"code": "codeA2", "campaign": "camp", "product_id": _uuid(), "business_id": _uuid()})
assert r.status_code == 200
r = client.post(f"/affiliates/{B}/links", headers={"X-Idempotency-Key": "link-B2", "X-Correlation-Id": "c-linkB"}, json={"code": "codeB2", "campaign": "camp", "product_id": _uuid(), "business_id": _uuid()})
assert r.status_code == 200

# Assign gold tier to B2
r = client.put(f"/admin/affiliates/{B}/tier", headers=headers_admin, json={"tier_name": "gold"})
print("assign tier status", r.status_code, r.text)

# Single paid order for each
for code in ("codeA2", "codeB2"):
    session_id = _uuid()
    buyer_phone = f"+260822{session_id[-6:]}"
    business_id = _uuid()
    order_id = _uuid()
    # click
    event_id = _uuid()
    r = client.post("/track/click", headers={"X-Idempotency-Key": event_id, "X-Correlation-Id": f"corr-click-{session_id}"}, json={"event_id": event_id, "affiliate_code": code, "session_id": session_id, "user_phone": buyer_phone})
    assert r.status_code == 200
    # attribute
    event_id = _uuid()
    r = client.post("/attribute/order", headers={"X-Idempotency-Key": event_id, "X-Correlation-Id": f"corr-attr-{order_id}"}, json={"event_id": event_id, "affiliate_code": code, "order_id": order_id, "business_id": business_id, "session_id": session_id, "user_phone": buyer_phone})
    assert r.status_code == 200
    # payment-success
    payload = {
        "event_id": _uuid(),
        "event_type": "payment_success",
        "occurred_at": "2026-01-24T00:00:00Z",
        "correlation_id": _uuid(),
        "producer": "payment-revenue",
        "payment_id": _uuid(),
        "order_id": order_id,
        "business_id": business_id,
        "user_phone": buyer_phone,
        "amount": 100.0,
        "currency": "ZMW",
        "earnings": {"msme_amount": 80.0, "affiliate_amount": 10.0, "platform_amount": 10.0, "affiliate_id": None, "affiliate_code": None},
    }
    r = client.post("/events/payment-success", headers={"X-Idempotency-Key": payload["event_id"], "X-Correlation-Id": payload["correlation_id"]}, json=payload)
    assert r.status_code == 200

# Get open epoch id
r = client.get("/admin/epochs", headers=headers_admin)
assert r.status_code == 200
epochs = r.json()
open_epochs = [e for e in epochs if e["status"] == "open"]
assert open_epochs
epoch_id = open_epochs[0]["id"]

# Set gross revenue
r = client.put(f"/admin/epochs/{epoch_id}/gross-revenue", headers=headers_admin, json={"gross_revenue_zmw": 1000.0})
print("set gross revenue", r.status_code, r.text)

# Call debug endpoint
r = client.get(f"/admin/epochs/{epoch_id}/debug-scores", headers=headers_admin)
print("debug status", r.status_code)
print(r.json())
