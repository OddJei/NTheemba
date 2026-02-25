import os
import json
import uuid
from datetime import datetime
from sqlalchemy import create_engine, text

DB_URL = os.getenv('DATABASE_URL', 'postgresql+psycopg2://postgres:!ladybug!#!@127.0.0.1:5432/ntheemba')
API_BASE = os.getenv('MSME_ENGINE_BASE', 'http://127.0.0.1:8570')

engine = create_engine(DB_URL)

def create_initiation(deposit_id: str, business_id: str, affiliate_id: str, amount_minor: int = 5000, currency: str = 'ZMW'):
    _id = str(uuid.uuid4())
    meta = {'amount_minor': amount_minor, 'currency': currency, 'subscription_id': str(uuid.uuid4())}
    now = datetime.utcnow()
    sql = text("""
    INSERT INTO msme_engine.payment_initiations (id, deposit_id, business_id, subscription_id, affiliate_id, metadata, status, created_at)
    VALUES (:id, :deposit_id, :business_id, :subscription_id, :affiliate_id, :metadata, :status, :created_at)
    """)
    with engine.begin() as conn:
        conn.execute(sql, {
            'id': _id,
            'deposit_id': deposit_id,
            'business_id': business_id,
            'subscription_id': meta['subscription_id'],
            'affiliate_id': affiliate_id,
            'metadata': json.dumps(meta),
            'status': 'pending',
            'created_at': now,
        })
    return _id


def trigger_callback(deposit_id: str, amount_minor: int = 5000, currency: str = 'ZMW'):
    try:
        import requests
    except Exception:
        raise RuntimeError('requests library required to call callback endpoint')

    payload = {
        'event_type': 'deposit.completed',
        'payment_id': deposit_id,
        'depositId': deposit_id,
        'amount_minor': amount_minor,
        'currency': currency,
        'status': 'completed',
    }
    url = f"{API_BASE}/callbacks/payments/deposits"
    r = requests.post(url, json=payload)
    print('callback response:', r.status_code, r.text)

    # fetch outbox pending
    r2 = requests.get(f"{API_BASE}/outbox/pending", headers={'X-Internal-Secret': 'test-internal-secret'})
    print('outbox pending status:', r2.status_code)
    try:
        print(json.dumps(r2.json(), indent=2))
    except Exception:
        print(r2.text)


if __name__ == '__main__':
    dep = os.getenv('DEPOSIT_ID') or str(uuid.uuid4())
    biz = os.getenv('BUSINESS_ID') or str(uuid.uuid4())
    aff = os.getenv('AFFILIATE_ID') or str(uuid.uuid4())
    print('Using deposit_id:', dep)
    print('business_id:', biz)
    print('affiliate_id:', aff)
    create_initiation(dep, biz, aff)
    trigger_callback(dep)
