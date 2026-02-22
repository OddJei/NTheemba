#!/usr/bin/env python3
"""Activate the business owner user using INTERNAL_SERVICE_SECRET, then
invoke the service-token helper to retry obtaining a service token.
"""
import json
import os
import subprocess
from urllib.parse import urljoin

try:
    import requests
except Exception:
    requests = None

OUT_DIR = os.environ.get('CONTRACT_OUT_DIR', 'contracts/msme-engine')
OWNER_ACT_PATH = os.path.join(OUT_DIR, 'responses', 'manual_activate_business.json')

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

def main():
    load_dotenv()
    if not os.path.exists(OWNER_ACT_PATH):
        raise SystemExit('manual_activate_business.json not found; run get_service_token_and_rerun first')
    with open(OWNER_ACT_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    owner_id = data.get('response', {}).get('owner_id')
    if not owner_id:
        raise SystemExit('owner_id not found in manual_activate_business.json')

    secret = os.environ.get('INTERNAL_SERVICE_SECRET') or os.environ.get('X_INTERNAL_SECRET')
    if not secret:
        raise SystemExit('No INTERNAL_SERVICE_SECRET in environment or .env')

    url = urljoin(os.environ.get('MSME_BASE_URL', 'http://localhost:8500'), f'/auth/user/{owner_id}')
    headers = {'X-Internal-Secret': secret, 'Content-Type': 'application/json'}
    body = {'is_active': True}
    if requests:
        resp = requests.put(url, json=body, headers=headers, timeout=10)
        status = resp.status_code
        try:
            resp_data = resp.json()
        except Exception:
            resp_data = resp.text
    else:
        import urllib.request
        req = urllib.request.Request(url, data=json.dumps(body).encode('utf-8'), method='PUT', headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                status = r.getcode()
                resp_data = json.loads(r.read().decode('utf-8'))
        except Exception as e:
            status = 0
            resp_data = str(e)

    out_path = os.path.join(OUT_DIR, 'responses', 'manual_activate_owner_direct.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({'status': status, 'response': resp_data}, f, indent=2, ensure_ascii=False)

    if 200 <= status < 300:
        print('Owner activated; invoking get_service_token_and_rerun to retry')
        subprocess.run(['python', 'scripts/get_service_token_and_rerun.py'], check=False)
    else:
        print('Owner activation failed; see', out_path)

if __name__ == '__main__':
    main()
