#!/usr/bin/env python3
"""Activate owner using INTERNAL_SERVICE_SECRET then immediately test PUT delivery-locations.
This avoids running the full generator which may deactivate users later in the run.
"""
import json
import os
from urllib.parse import urljoin
try:
    import requests
except Exception:
    requests = None

OUT_DIR = os.environ.get('CONTRACT_OUT_DIR', 'contracts/msme-engine')
BUS_ACT_PATH = os.path.join(OUT_DIR, 'responses', 'manual_activate_business.json')

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

def activate_owner(owner_id):
    secret = os.environ.get('INTERNAL_SERVICE_SECRET') or os.environ.get('X_INTERNAL_SECRET')
    if not secret:
        raise SystemExit('INTERNAL_SERVICE_SECRET not found')
    url = urljoin(os.environ.get('MSME_BASE_URL', 'http://localhost:8500'), f'/auth/user/{owner_id}')
    headers = {'X-Internal-Secret': secret, 'Content-Type': 'application/json'}
    body = {'is_active': True}
    if requests:
        r = requests.put(url, json=body, headers=headers, timeout=10)
        return r.status_code, r.text
    else:
        import urllib.request
        req = urllib.request.Request(url, data=json.dumps(body).encode('utf-8'), method='PUT', headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as rr:
                return rr.getcode(), rr.read().decode('utf-8')
        except Exception as e:
            return 0, str(e)

def main():
    load_dotenv()
    if not os.path.exists(BUS_ACT_PATH):
        raise SystemExit('manual_activate_business.json not found')
    with open(BUS_ACT_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    owner_id = data.get('response', {}).get('owner_id')
    if not owner_id:
        raise SystemExit('owner_id missing')

    status, resp = activate_owner(owner_id)
    print('Activate owner status:', status)
    print(resp)

    # run the PUT test directly
    subprocess_cmd = ['python', 'scripts/test_put_delivery_locations.py']
    import subprocess
    subprocess.run(subprocess_cmd, check=False)

if __name__ == '__main__':
    main()
