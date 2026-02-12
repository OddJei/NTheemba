#!/usr/bin/env python3
"""Test exact payload from outbox"""
import httpx
import json

payload = {"event_id": "order-created-efa6eb6a-20e4-47e4-8375-8a59d4c9a39e", "event_type": "order_created", "occurred_at": "2026-02-03T05:51:04.899402Z", "correlation_id": "93e275f1-247f-484a-bd69-192744f63072", "producer": "order-delivery", "order_id": "efa6eb6a-20e4-47e4-8375-8a59d4c9a39e", "business_id": "a305ddb9-4432-4b7d-9e75-4225391f8bb4", "status": "pending_payment", "total_amount": 100000.0, "currency": "ZMW", "session_id": None, "user_phone": "260973456789", "user_id": None, "affiliate_code": "TESTCODE123", "affiliate_id": "aff-xyz-789", "metadata": {"affiliate_id": "aff-xyz-789", "affiliate_code": "TESTCODE123", "transaction_fee_pct": 0.05, "platform_fee_amount": 5000, "msme_net_amount": 95000, "fee_source": "msme_entitlements"}, "transaction_fee_pct": 0.05, "platform_fee_amount": 5000, "msme_net_amount": 95000}

try:
    r = httpx.post(
        'http://127.0.0.1:8510/events/order-created',
        json=payload,
        timeout=5
    )
    print(f'Status: {r.status_code}')
    print(f'Response: {r.text[:500]}')
except Exception as e:
    print(f'Error: {type(e).__name__}: {e}')
