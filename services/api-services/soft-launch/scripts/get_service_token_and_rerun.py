#!/usr/bin/env python3
"""Obtain a service-token for the seeded business using the manual login
access token, save the response, and re-run the generator with the service
token to test protected endpoints (delivery-locations).

Run from repo root:
    python scripts/get_service_token_and_rerun.py
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


def _load_dotenv_if_missing():
    env_path = os.path.join(os.getcwd(), '.env')
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                k = k.strip()
                v = v.strip()
                if k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass


# try to source .env so INTERNAL_SERVICE_SECRET / X_INTERNAL_SECRET are available
_load_dotenv_if_missing()

manual_login_path = os.path.join(OUT_DIR, 'responses', 'manual_login.json')
service_out = os.path.join(OUT_DIR, 'responses', 'manual_service_token.json')
seed_ids_path = os.path.join(OUT_DIR, 'seed_ids.json')

def read_manual_login():
    if not os.path.exists(manual_login_path):
        raise SystemExit(f"Manual login response not found at {manual_login_path}")
    with open(manual_login_path, 'r', encoding='utf-8') as f:
        j = json.load(f)
    return j.get('response') or {}

def read_seed_ids():
    if not os.path.exists(seed_ids_path):
        return {}
    try:
        with open(seed_ids_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def request_service_token(business_id, access_token):
    url = urljoin(BASE, f"/auth/service-token/{business_id}")
    headers = {'Authorization': f'Bearer {access_token}'}
    if requests:
        resp = requests.post(url, headers=headers, timeout=10)
        status = resp.status_code
        try:
            data = resp.json()
        except Exception:
            data = resp.text
    else:
        import urllib.request
        req = urllib.request.Request(url, method='POST', headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                status = r.getcode()
                data = json.loads(r.read().decode('utf-8'))
        except Exception as e:
            status = 0
            data = str(e)
    return status, data


def activate_business(business_id, access_token):
    url = urljoin(BASE, f"/business/{business_id}")
    headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
    body = {'is_active': True}
    if requests:
        resp = requests.put(url, json=body, headers=headers, timeout=10)
        status = resp.status_code
        try:
            data = resp.json()
        except Exception:
            data = resp.text
    else:
        import urllib.request
        req = urllib.request.Request(url, data=json.dumps(body).encode('utf-8'), method='PUT', headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                status = r.getcode()
                data = json.loads(r.read().decode('utf-8'))
        except Exception as e:
            status = 0
            data = str(e)
    return status, data

def main():
    login = read_manual_login()
    # access token parsed from manual_login save
    access = None
    if isinstance(login, dict):
        access = login.get('access_token') or login.get('token') or login.get('jwt')
    if not access:
        raise SystemExit('No access token found in manual login response')

    seeds = read_seed_ids()
    business_id = seeds.get('business_id') or seeds.get('id')
    if not business_id:
        # try to find a business id in POST_auth_register or GET_business__id
        maybe = os.path.join(OUT_DIR, 'responses', 'POST_auth_register.json')
        if os.path.exists(maybe):
            with open(maybe, 'r', encoding='utf-8') as f:
                jr = json.load(f)
            # register contains user info; business may be null
            business_id = jr.get('response', {}).get('business_id')
    if not business_id:
        raise SystemExit('No business_id available in seed_ids or register response')

    print('Requesting service-token for business:', business_id)
    status, data = request_service_token(business_id, access)
    out = {'method': 'POST', 'path': f'/auth/service-token/{business_id}', 'url': urljoin(BASE, f'/auth/service-token/{business_id}'), 'status': status, 'response': data}
    with open(service_out, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    token = None
    if isinstance(data, dict):
        token = data.get('access_token') or data.get('token') or data.get('jwt')

    # If business inactive, attempt to activate and retry
    if not token:
        reason = None
        if isinstance(data, dict):
            reason = data.get('detail')
        if status == 403 and reason == 'business_inactive':
            print('Business inactive. Attempting to activate business...')
            act_status, act_data = activate_business(business_id, access)
            act_out_path = os.path.join(OUT_DIR, 'responses', 'manual_activate_business.json')
            with open(act_out_path, 'w', encoding='utf-8') as f:
                json.dump({'status': act_status, 'response': act_data}, f, indent=2, ensure_ascii=False)
            if 200 <= act_status < 300:
                print('Activation succeeded, retrying service-token request...')
                status, data = request_service_token(business_id, access)
                out = {'method': 'POST', 'path': f'/auth/service-token/{business_id}', 'url': urljoin(BASE, f'/auth/service-token/{business_id}'), 'status': status, 'response': data}
                with open(service_out, 'w', encoding='utf-8') as f:
                    json.dump(out, f, indent=2, ensure_ascii=False)
                if isinstance(data, dict):
                    token = data.get('access_token') or data.get('token') or data.get('jwt')
        # If still no token, try using internal service secret header if available
        if not token:
            secret = os.environ.get('INTERNAL_SERVICE_SECRET') or os.environ.get('X_INTERNAL_SECRET')
            if secret:
                print('Attempting service-token request using INTERNAL_SERVICE_SECRET header...')
                url = urljoin(BASE, f"/auth/service-token/{business_id}")
                headers = {'X-Internal-Secret': secret}
                if requests:
                    resp = requests.post(url, headers=headers, timeout=10)
                    st = resp.status_code
                    try:
                        dt = resp.json()
                    except Exception:
                        dt = resp.text
                else:
                    import urllib.request
                    req = urllib.request.Request(url, method='POST', headers=headers)
                    try:
                        with urllib.request.urlopen(req, timeout=10) as r:
                            st = r.getcode()
                            dt = json.loads(r.read().decode('utf-8'))
                    except Exception as e:
                        st = 0
                        dt = str(e)
                # save override
                out = {'method': 'POST', 'path': f'/auth/service-token/{business_id}', 'url': url, 'status': st, 'response': dt}
                with open(service_out, 'w', encoding='utf-8') as f:
                    json.dump(out, f, indent=2, ensure_ascii=False)
                if isinstance(dt, dict):
                    token = dt.get('access_token') or dt.get('token') or dt.get('jwt')
                if not token:
                    print('Service-token request with internal secret failed (status', st, '). Aborting.')
                    return
        # If still failing due to owner_inactive, attempt to activate owner using internal secret
        # (some deployments require internal activation of owner user)
        if not token and isinstance(data, dict) and data.get('detail') == 'owner_inactive':
            owner_id = None
            # try to fetch owner id from last activation response
            act_path = os.path.join(OUT_DIR, 'responses', 'manual_activate_business.json')
            if os.path.exists(act_path):
                try:
                    with open(act_path, 'r', encoding='utf-8') as f:
                        act = json.load(f)
                    owner_id = act.get('response', {}).get('owner_id')
                except Exception:
                    owner_id = None
            if owner_id:
                secret = os.environ.get('INTERNAL_SERVICE_SECRET') or os.environ.get('X_INTERNAL_SECRET')
                if secret:
                    print('Attempting to activate owner user:', owner_id)
                    url = urljoin(BASE, f"/auth/user/{owner_id}")
                    headers = {'X-Internal-Secret': secret, 'Content-Type': 'application/json'}
                    body = {'is_active': True}
                    if requests:
                        resp = requests.put(url, json=body, headers=headers, timeout=10)
                        ost = resp.status_code
                        odt = None
                        try:
                            odt = resp.json()
                        except Exception:
                            odt = resp.text
                    else:
                        import urllib.request
                        req = urllib.request.Request(url, data=json.dumps(body).encode('utf-8'), method='PUT', headers=headers)
                        try:
                            with urllib.request.urlopen(req, timeout=10) as r:
                                ost = r.getcode()
                                odt = json.loads(r.read().decode('utf-8'))
                        except Exception as e:
                            ost = 0
                            odt = str(e)
                    owner_out = os.path.join(OUT_DIR, 'responses', 'manual_activate_owner.json')
                    with open(owner_out, 'w', encoding='utf-8') as f:
                        json.dump({'status': ost, 'response': odt}, f, indent=2, ensure_ascii=False)
                    if 200 <= ost < 300:
                        print('Owner activated; retrying service-token request using internal secret...')
                        # try internal secret again
                        secret = secret
                        url = urljoin(BASE, f"/auth/service-token/{business_id}")
                        headers = {'X-Internal-Secret': secret}
                        if requests:
                            resp = requests.post(url, headers=headers, timeout=10)
                            st = resp.status_code
                            try:
                                dt = resp.json()
                            except Exception:
                                dt = resp.text
                        else:
                            import urllib.request
                            req = urllib.request.Request(url, method='POST', headers=headers)
                            try:
                                with urllib.request.urlopen(req, timeout=10) as r:
                                    st = r.getcode()
                                    dt = json.loads(r.read().decode('utf-8'))
                            except Exception as e:
                                st = 0
                                dt = str(e)
                        out = {'method': 'POST', 'path': f'/auth/service-token/{business_id}', 'url': url, 'status': st, 'response': dt}
                        with open(service_out, 'w', encoding='utf-8') as f:
                            json.dump(out, f, indent=2, ensure_ascii=False)
                        if isinstance(dt, dict):
                            token = dt.get('access_token') or dt.get('token') or dt.get('jwt')
                else:
                    print('No INTERNAL_SERVICE_SECRET available to activate owner.')
            else:
                print('Service-token request did not return a token (status', status, '). Aborting generator re-run.')
                return

    print('Re-running generator with obtained service-token...')
    env = os.environ.copy()
    env['MSME_SERVICE_TOKEN'] = token
    # keep existing seed ids
    if os.path.exists(seed_ids_path):
        try:
            with open(seed_ids_path, 'r', encoding='utf-8') as f:
                env['CONTRACT_SEED_IDS'] = json.dumps(json.load(f))
        except Exception:
            pass

    # ensure environment values are all strings for subprocess
    env = {str(k): str(v) for k, v in env.items() if v is not None}
    subprocess.run(['python', 'scripts/generate_contracts_msme.py'], env=env, check=False)

if __name__ == '__main__':
    main()
