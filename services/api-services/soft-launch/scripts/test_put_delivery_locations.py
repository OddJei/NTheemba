#!/usr/bin/env python3
"""Test PUT /businesses/{business_id}/delivery-locations using a crafted
owner access token and print the response for debugging.
"""
import json
import os
import hmac
import hashlib
import base64
import datetime as dt
try:
    import requests
except Exception:
    requests = None

OUT_DIR = os.environ.get('CONTRACT_OUT_DIR', 'contracts/msme-engine')
BUS_ACT_PATH = os.path.join(OUT_DIR, 'responses', 'manual_activate_business.json')

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode('ascii')

def craft_jwt(owner_id: str, business_id: str, secret: str, minutes: int = 60):
    header = {'alg': 'HS256', 'typ': 'JWT'}
    now = dt.datetime.now(dt.timezone.utc)
    exp = now + dt.timedelta(minutes=minutes)
    payload = {
        'sub': owner_id,
        'role': 'default',
        'business_id': business_id,
        'affiliate_id': None,
        'iat': int(now.timestamp()),
        'exp': int(exp.timestamp()),
        'typ': 'access',
    }
    header_b = _b64url_encode(json.dumps(header, separators=(',', ':'), sort_keys=True).encode('utf-8'))
    payload_b = _b64url_encode(json.dumps(payload, separators=(',', ':'), sort_keys=True).encode('utf-8'))
    signing_input = f"{header_b}.{payload_b}".encode('ascii')
    sig = hmac.new(secret.encode('utf-8'), signing_input, hashlib.sha256).digest()
    sig_b = _b64url_encode(sig)
    return f"{header_b}.{payload_b}.{sig_b}"

def main():
    if not os.path.exists(BUS_ACT_PATH):
        raise SystemExit('manual_activate_business.json not found')
    with open(BUS_ACT_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    owner_id = data.get('response', {}).get('owner_id')
    business_id = data.get('response', {}).get('id')
    if not owner_id or not business_id:
        raise SystemExit('owner_id or business_id missing')

    secret = os.environ.get('MSME_JWT_SECRET')
    if not secret:
        # attempt to load from .env
        env_path = os.path.join(os.getcwd(), '.env')
        if os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    k, v = line.split('=', 1)
                    if k == 'MSME_JWT_SECRET':
                        secret = v.strip()
                        break
    if not secret:
        raise SystemExit('MSME_JWT_SECRET not found')

    token = craft_jwt(owner_id, business_id, secret)
    print('Token:', token)
    # test auth/me with token
    me_url = 'http://localhost:8500/auth/me'
    if requests:
        m = requests.get(me_url, headers={'Authorization': f'Bearer {token}'}, timeout=10)
        print('GET /auth/me ->', m.status_code)
        try:
            print(m.json())
        except Exception:
            print(m.text)
    else:
        import urllib.request
        req = urllib.request.Request(me_url, headers={'Authorization': f'Bearer {token}'})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                print('GET /auth/me ->', r.getcode())
                print(r.read().decode('utf-8'))
        except Exception as e:
            print('GET /auth/me error:', e)

    url = f"http://localhost:8500/businesses/{business_id}/delivery-locations"
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    body = {'delivery_locations': {'Lusaka': {'price_minor': 2500, 'currency': 'ZMW'}}}
    if requests:
        resp = requests.put(url, json=body, headers=headers, timeout=10)
        print(resp.status_code)
        try:
            print(resp.json())
        except Exception:
            print(resp.text)
    else:
        import urllib.request
        req = urllib.request.Request(url, data=json.dumps(body).encode('utf-8'), method='PUT', headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                print(r.getcode())
                print(r.read().decode('utf-8'))
        except Exception as e:
            print('Error:', e)

if __name__ == '__main__':
    main()
