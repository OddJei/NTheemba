#!/usr/bin/env python3
"""Test affiliate-engine endpoint"""
import httpx
import json

payload = {
    'order_id': 'test-order-123',
    'affiliate_code': 'TEST123',
    'affiliate_id': 'aff-test-001',
}

try:
    r = httpx.post(
        'http://soft-launch-affiliate-engine-1:8510/events/order-created',
        json=payload,
        timeout=2
    )
    print(f'Status: {r.status_code}')
    print(f'Response: {r.text}')
except Exception as e:
    print(f'Error: {type(e).__name__}: {e}')
