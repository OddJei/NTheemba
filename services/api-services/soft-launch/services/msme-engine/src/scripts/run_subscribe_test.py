import os
import uuid
import httpx
import sys

BASE = os.getenv('BASE_URL', 'http://127.0.0.1:8500')
INTERNAL = os.getenv('OUTBOX_INTERNAL_SECRET', 'test-internal-secret')

print('BASE:', BASE)
print('INTERNAL secret:', INTERNAL)

with httpx.Client(timeout=30.0) as c:
    try:
        print('\nGET /internal/businesses')
        r = c.get(f'{BASE}/internal/businesses', headers={'X-Internal-Secret': INTERNAL})
        print('status', r.status_code)
        print(r.text[:1000])
        bs = r.json() if r.status_code == 200 else None
    except Exception as e:
        print('internal/businesses request failed:', e)
        sys.exit(1)

    if not bs:
        print('no businesses returned; aborting')
        sys.exit(2)

    biz = bs[0]['id']
    print('\nselected business id:', biz)

    # register
    un = f'tc_{uuid.uuid4().hex[:6]}'
    email = f'tc+{uuid.uuid4().hex[:6]}@example.com'
    pwd = 'secret123'
    reg_payload = {'username': un, 'email': email, 'password': pwd, 'phone': '+260971000999', 'role': 'msme'}
    print('\nPOST /auth/register', reg_payload)
    r = c.post(f'{BASE}/auth/register', json=reg_payload)
    print('status', r.status_code)
    print(r.text[:2000])

    # login
    print('\nPOST /auth/login')
    r = c.post(f'{BASE}/auth/login', json={'identifier': email, 'password': pwd})
    print('status', r.status_code)
    print(r.text[:2000])
    if r.status_code != 200:
        print('login failed; aborting')
        sys.exit(3)
    tok = r.json().get('access_token')
    if not tok:
        print('no access token returned; aborting')
        sys.exit(4)

    headers = {'Authorization': f'Bearer {tok}'}

    # subscribe and pay (paid payload)
    payload = {'plan': 'paid', 'amount_minor': 5000, 'currency': 'ZMW', 'phone_number': '+260971000000', 'provider': 'pawapay'}
    print(f"\nPOST /business/{biz}/subscribe_and_pay payload:", payload)
    r = c.post(f'{BASE}/business/{biz}/subscribe_and_pay', json=payload, headers=headers)
    print('status', r.status_code)
    print(r.text[:4000])

    # check outbox pending
    print('\nGET /outbox/pending')
    r = c.get(f'{BASE}/outbox/pending', headers={'X-Internal-Secret': INTERNAL})
    print('status', r.status_code)
    try:
        j = r.json()
        print('outbox rows:', len(j))
        if j:
            import json
            print(json.dumps(j[:5], indent=2))
    except Exception:
        print('could not parse outbox response')
        print(r.text)

print('\nDone')
