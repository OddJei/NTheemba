#!/usr/bin/env python3
"""Craft an owner access token using the MSME_JWT_SECRET and re-run the
generator with that token as MSME_SERVICE_TOKEN so user-authenticated
endpoints (like delivery-locations PUT) run as the owner.
"""
import json
import os
import hmac
import hashlib
import base64
import datetime as dt
import subprocess
from urllib.parse import urljoin

OUT_DIR = os.environ.get('CONTRACT_OUT_DIR', 'contracts/msme-engine')
BUS_ACT_PATH = os.path.join(OUT_DIR, 'responses', 'manual_activate_business.json')

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode('ascii')

def load_dotenv():
    env_path = os.path.join(os.getcwd(), '.env')
    if not os.path.exists(env_path):
        return
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            if k not in os.environ:
                os.environ[k] = v.strip()

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
    load_dotenv()
    if not os.path.exists(BUS_ACT_PATH):
        raise SystemExit('manual_activate_business.json not found; run previous steps')
    with open(BUS_ACT_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    owner_id = data.get('response', {}).get('owner_id')
    business_id = data.get('response', {}).get('id')
    if not owner_id or not business_id:
        raise SystemExit('owner_id or business_id missing in manual_activate_business.json')

    secret = os.environ.get('MSME_JWT_SECRET')
    if not secret:
        raise SystemExit('MSME_JWT_SECRET not found in environment or .env')

    token = craft_jwt(owner_id, business_id, secret)
    print('Crafted owner token for', owner_id)

    env = os.environ.copy()
    env['MSME_SERVICE_TOKEN'] = token
    # keep existing seed ids if present
    seed_path = os.path.join(OUT_DIR, 'seed_ids.json')
    if os.path.exists(seed_path):
        try:
            with open(seed_path, 'r', encoding='utf-8') as f:
                env['CONTRACT_SEED_IDS'] = json.dumps(json.load(f))
        except Exception:
            pass

    # ensure env values are strings
    env = {str(k): str(v) for k, v in env.items() if v is not None}
    subprocess.run(['python', 'scripts/generate_contracts_msme.py'], env=env, check=False)

if __name__ == '__main__':
    main()
