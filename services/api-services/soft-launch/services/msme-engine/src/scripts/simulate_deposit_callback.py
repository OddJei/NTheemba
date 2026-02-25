import httpx
import json

base = 'http://127.0.0.1:8570'
# Replace these values if different
deposit_id = '1f619112-c938-45a4-84d2-21d32600796c'
business_id = '942a458c-da6d-473c-85b3-2c1cdebed0a2'

payload = {
    'event_type': 'deposit.completed',
    'event_id': 'evt-' + deposit_id,
    'depositId': deposit_id,
    'business_id': business_id,
    'amount_minor': 5000,
    'currency': 'ZMW',
    'status': 'completed',
}

print('POSTing deposit callback:', json.dumps(payload))
with httpx.Client(timeout=30.0) as c:
    r = c.post(f'{base}/callbacks/payments/deposits', json=payload)
    print('deposit callback status', r.status_code)
    print('resp:', r.text)

    r2 = c.get(f'{base}/outbox/pending', headers={'X-Internal-Secret': 'test-internal-secret'})
    print('outbox status', r2.status_code)
    try:
        print(json.dumps(r2.json(), indent=2))
    except Exception:
        print('could not parse outbox response')
        print(r2.text)
