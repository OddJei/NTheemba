#!/usr/bin/env python3
"""Perform a manual login using the saved register response, capture tokens,
save the login response, then re-run the contract generator with the obtained
access token and seeded refresh token.

Run from repo root:
    python scripts/manual_login_and_rerun.py
"""
import json
import os
import subprocess
from urllib.parse import urljoin

try:
    import requests
except Exception:
    requests = None

BASE = os.environ.get("MSME_BASE_URL", "http://localhost:8500")
OUT_DIR = os.environ.get("CONTRACT_OUT_DIR", "contracts/msme-engine")

register_path = os.path.join(OUT_DIR, 'responses', 'POST_auth_register.json')
manual_out = os.path.join(OUT_DIR, 'responses', 'manual_login.json')
seed_ids_path = os.path.join(OUT_DIR, 'seed_ids.json')

def read_register():
    if not os.path.exists(register_path):
        raise SystemExit(f"Register response not found at {register_path}")
    with open(register_path, 'r', encoding='utf-8') as f:
        j = json.load(f)
    return j.get('response') or {}

def do_login(identifier, password):
    login_url = urljoin(BASE, '/auth/login')
    body = {'identifier': identifier, 'password': password}
    if requests:
        resp = requests.post(login_url, json=body, timeout=10)
        status = resp.status_code
        try:
            data = resp.json()
        except Exception:
            data = resp.text
    else:
        import urllib.request
        req = urllib.request.Request(login_url, data=json.dumps(body).encode('utf-8'), headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                status = r.getcode()
                data = json.loads(r.read().decode('utf-8'))
        except Exception as e:
            status = 0
            data = str(e)
    return status, data

def main():
    reg = read_register()
    identifier = reg.get('phone') or reg.get('email') or reg.get('username')
    if not identifier:
        raise SystemExit('No identifier found in register response')
    password = os.environ.get('MSME_MANUAL_PASSWORD', 'Passw0rd!')

    print('Logging in with', identifier)
    status, data = do_login(identifier, password)
    out = {'method': 'POST', 'path': '/auth/login', 'url': urljoin(BASE, '/auth/login'), 'status': status, 'response': data}
    with open(manual_out, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    access_token = None
    refresh_token = None
    if isinstance(data, dict):
        access_token = data.get('access_token') or data.get('token') or data.get('jwt')
        refresh_token = data.get('refresh_token') or data.get('refreshToken') or data.get('refresh')

    if not access_token:
        print('No access token received (status', status, '). Saved manual login response. Aborting generator re-run.')
        return

    # prepare seed ids (include refresh token if we have one)
    seed_ids = {}
    if os.path.exists(seed_ids_path):
        try:
            with open(seed_ids_path, 'r', encoding='utf-8') as f:
                seed_ids = json.load(f)
        except Exception:
            seed_ids = {}
    if refresh_token:
        seed_ids['refresh_token'] = refresh_token

    # run generator with MSME_SERVICE_TOKEN and CONTRACT_SEED_IDS
    env = os.environ.copy()
    env['MSME_SERVICE_TOKEN'] = access_token
    env['CONTRACT_SEED_IDS'] = json.dumps(seed_ids)

    print('Re-running generator with MSME_SERVICE_TOKEN and CONTRACT_SEED_IDS...')
    cmd = ['python', 'scripts/generate_contracts_msme.py']
    subprocess.run(cmd, env=env, check=False)

if __name__ == '__main__':
    main()
