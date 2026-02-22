#!/usr/bin/env python3
"""Generate contracts and capture responses for msme-engine endpoints.

Saves OpenAPI contract and per-endpoint response samples + inferred JSON schema.

Run from repo root:
    python scripts/generate_contracts_msme.py
"""
import json
import os
import re
import sys
import time
import math
from urllib.parse import urljoin

try:
    import requests
except Exception:
    requests = None

BASE = os.environ.get("MSME_BASE_URL", "http://localhost:8500")
OUT_DIR = os.environ.get("CONTRACT_OUT_DIR", "contracts/msme-engine")
AUTH_USER = os.environ.get("MSME_AUTH_USER")
AUTH_PASS = os.environ.get("MSME_AUTH_PASS")
SERVICE_TOKEN = os.environ.get("MSME_SERVICE_TOKEN")
X_INTERNAL_SECRET = os.environ.get("X_INTERNAL_SECRET")
RETRY_ATTEMPTS = int(os.environ.get("CONTRACT_RETRY_ATTEMPTS", "3"))
RETRY_BACKOFF_BASE = float(os.environ.get("CONTRACT_RETRY_BACKOFF_BASE", "1.0"))
# Seed IDs mapping: JSON string like '{"business_id":"abc","user_id":"u1"}'
SEED_IDS = os.environ.get("CONTRACT_SEED_IDS", '{}')
try:
    SEED_IDS = json.loads(SEED_IDS)
except Exception:
    SEED_IDS = {}

# If no seed ids provided via env, try loading from OUT_DIR/seed_ids.json
try:
    if not SEED_IDS:
        seed_file = os.path.join(OUT_DIR, 'seed_ids.json')
        if os.path.exists(seed_file):
            with open(seed_file, 'r', encoding='utf-8') as sf:
                SEED_IDS = json.load(sf)
except Exception:
    pass

# By default do NOT run destructive operations (DELETE). Set
# CONTRACT_ALLOW_DESTRUCTIVE=true to opt-in to destructive calls.
ALLOW_DESTRUCTIVE = os.environ.get('CONTRACT_ALLOW_DESTRUCTIVE', 'false').lower() in ('1', 'true', 'yes')
# Optionally run only an explicit safe whitelist of endpoints (useful for CI)
WHITELIST_ONLY = os.environ.get('CONTRACT_WHITELIST_ONLY', 'false').lower() in ('1', 'true', 'yes')

# Default safe whitelist (method,path) patterns when WHITELIST_ONLY is enabled
DEFAULT_WHITELIST = [
    ('GET', '/outbox/pending'),
    ('POST', '/outbox/ack'),
    ('GET', '/businesses/{business_id}/delivery-locations'),
    ('PUT', '/businesses/{business_id}/delivery-locations'),
    ('POST', '/auth/service-token'),
    ('GET', '/auth/me'),
    ('POST', '/events/payment_failed'),
    ('POST', '/events/payment_success'),
    ('GET', '/health'),
    ('GET', '/metrics'),
    ('POST', '/notification/send'),
]

os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(os.path.join(OUT_DIR, "responses"), exist_ok=True)


def _load_dotenv_if_missing():
    # If key env vars aren't present in the environment (e.g. when running
    # the script from the repo root without sourcing .env), attempt to load
    # simple KEY=VALUE pairs from a top-level .env file.
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
                # only set variables that are not already present
                if k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass


# ensure .env is read so X_INTERNAL_SECRET and friends are available
_load_dotenv_if_missing()

# refresh from environment after potential .env load
X_INTERNAL_SECRET = os.environ.get("X_INTERNAL_SECRET")
MSME_JWT_SECRET = os.environ.get('MSME_JWT_SECRET')


def _requests_session():
    if requests:
        s = requests.Session()
        return s
    return None


def http_get(url, headers=None):
    headers = headers or {}
    if requests:
        return requests.get(url, timeout=10, headers=headers)
    import urllib.request
    req = urllib.request.Request(url, method='GET', headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        class R:
            status_code = resp.getcode()
            headers = dict(resp.getheaders())
            text = resp.read().decode('utf-8')
            def json(self):
                return json.loads(self.text)
        return R()


def http_request(method, url, json_body=None, headers=None):
    headers = headers or {}
    if requests:
        fn = getattr(requests, method.lower())
        return fn(url, json=json_body, timeout=10, headers=headers)
    import urllib.request
    data = None
    req_headers = headers.copy()
    if json_body is not None:
        data = json.dumps(json_body).encode('utf-8')
        req_headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, method=method.upper(), headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            class R:
                status_code = resp.getcode()
                headers = dict(resp.getheaders())
                text = resp.read().decode('utf-8')
                def json(self):
                    return json.loads(self.text)
            return R()
    except Exception as e:
        class E:
            status_code = 0
            headers = {}
            text = str(e)
            def json(self):
                raise
        return E()


def sanitize_path(path):
    return re.sub(r"[^0-9A-Za-z_.-]", "_", path).strip("_")


def sample_from_schema(schema: dict):
    typ = schema.get('type')
    if not typ and 'properties' in schema:
        typ = 'object'
    if typ == 'object':
        obj = {}
        for k, v in schema.get('properties', {}).items():
            obj[k] = sample_from_schema(v)
        return obj
    if typ == 'array':
        items = schema.get('items', {'type': 'string'})
        return [sample_from_schema(items)]
    if typ == 'integer' or typ == 'number':
        return 1
    if typ == 'boolean':
        return True
    return schema.get('example') or schema.get('default') or "string"


def infer_schema_from_value(value):
    if value is None:
        return {'type': 'null'}
    if isinstance(value, bool):
        return {'type': 'boolean'}
    if isinstance(value, int) and not isinstance(value, bool):
        return {'type': 'integer'}
    if isinstance(value, float):
        return {'type': 'number'}
    if isinstance(value, str):
        return {'type': 'string'}
    if isinstance(value, list):
        if not value:
            return {'type': 'array', 'items': {}}
        return {'type': 'array', 'items': infer_schema_from_value(value[0])}
    if isinstance(value, dict):
        props = {k: infer_schema_from_value(v) for k, v in value.items()}
        return {'type': 'object', 'properties': props}
    return {'type': 'string'}


def populate_path_with_seeds(path):
    # replace {param} with seed value if present else 'test'
    def repl(m):
        name = m.group(1)
        return str(SEED_IDS.get(name, 'test'))
    return re.sub(r"\{([^}]+)\}", repl, path)


def craft_jwt_for_user(user_id: str, business_id: str | None, secret: str, minutes: int = 60):
    # Minimal JWT HS256 creation compatible with msme-engine
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    exp = now + (minutes * 60)
    payload = {
        "sub": user_id,
        "role": "default",
        "business_id": business_id,
        "affiliate_id": None,
        "iat": now,
        "exp": exp,
        "typ": "access",
    }
    def b64(u: bytes) -> str:
        return re.sub('=+$', '', base64.urlsafe_b64encode(u).decode('ascii'))
    import base64, hmac, hashlib
    header_b = b64(json.dumps(header, separators=(",", ":"), sort_keys=True).encode('utf-8'))
    payload_b = b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode('utf-8'))
    signing_input = f"{header_b}.{payload_b}".encode('ascii')
    sig = hmac.new(secret.encode('utf-8'), signing_input, hashlib.sha256).digest()
    sig_b = b64(sig)
    return f"{header_b}.{payload_b}.{sig_b}"


def get_override_for_endpoint(method, path, seeds):
    # Return (body, extra_headers) for specific endpoints to satisfy validation
    extra_headers = {}
    body = None
    bid = seeds.get('business_id') or seeds.get('id')
    uid = seeds.get('user_id')
    phone = seeds.get('phone_number')
    msme_code = seeds.get('msme_code')

    if method == 'POST' and path.endswith('/callbacks/payments/deposits'):
        body = {
            'event_type': 'deposit.completed',
            'event_id': f'evt_{int(time.time())}',
            'payment_id': seeds.get('payment_id', 'pay_test_123'),
            'business_id': bid,
            'amount_minor': seeds.get('amount_minor', 5000),
            'currency': 'ZMW',
            'status': 'completed',
        }

    if method == 'POST' and path.endswith('/callbacks/payments/payouts'):
        body = {
            'event_type': 'payout.completed',
            'event_id': f'evt_{int(time.time())}',
            'depositId': seeds.get('depositId', 'dep_test_123'),
            'business_id': bid,
            'amount_minor': seeds.get('amount_minor', 10000),
            'currency': 'ZMW',
            'status': 'completed',
        }

    if method == 'POST' and path.endswith('/outbox/ack'):
        body = {'ids': seeds.get('outbox_ids', ['out_test_1'])}
        # outbox ack requires internal secret
        if X_INTERNAL_SECRET:
            extra_headers['X-Internal-Secret'] = X_INTERNAL_SECRET
        if SERVICE_TOKEN:
            extra_headers['Authorization'] = f'Bearer {SERVICE_TOKEN}'

    if method == 'GET' and path.endswith('/outbox/pending'):
        # outbox listing also requires internal secret
        if X_INTERNAL_SECRET:
            extra_headers['X-Internal-Secret'] = X_INTERNAL_SECRET
        if SERVICE_TOKEN:
            extra_headers['Authorization'] = f'Bearer {SERVICE_TOKEN}'

    if method == 'POST' and '/business/' in path and path.endswith('/subscribe_and_pay'):
        body = {
            # prefer seeded plan, fallback to 'starter' instead of hardcoded 'basic'
            'plan': seeds.get('plan', 'starter'),
            'amount_minor': seeds.get('amount_minor', 2500),
            'currency': 'ZMW',
            'phone_number': phone or seeds.get('phone'),
            'provider': 'pawapay'
        }
        if SERVICE_TOKEN:
            extra_headers['Authorization'] = f'Bearer {SERVICE_TOKEN}'

    if method == 'POST' and '/business/' in path and path.endswith('/subscribe'):
        body = {'plan': seeds.get('plan', 'starter')}
        if SERVICE_TOKEN:
            extra_headers['Authorization'] = f'Bearer {SERVICE_TOKEN}'

    # Ensure auth endpoints send JSON objects (some generator runs sent strings)
    if method == 'POST' and path.endswith('/auth/register'):
        body = {
            'phone': phone or f'testuser_{int(time.time())}@example.com',
            'password': seeds.get('auth_password', 'Passw0rd!'),
            'name': seeds.get('name', 'Test User'),
            'username': seeds.get('username', f'user_{int(time.time())}'),
            'email': seeds.get('email', f'user_{int(time.time())}@example.com'),
        }

    if method == 'POST' and path.endswith('/auth/login'):
        body = {
            'identifier': phone or f'testuser_{int(time.time())}@example.com',
            'password': seeds.get('auth_password', 'Passw0rd!'),
        }

    if method == 'POST' and path.endswith('/auth/refresh'):
        # prefer a seeded refresh token if available
        body = {
            'refresh_token': seeds.get('refresh_token', ''),
        }

    if method == 'POST' and path.endswith('/auth/logout'):
        # logout may expect a JSON body or Authorization header; send empty JSON
        body = {}

    if method == 'POST' and path.endswith('/events/payment_success'):
        # Some callers pass amount as a numeric value; sample as numeric converted from minor
        amount_minor = seeds.get('amount_minor', 2500)
        amount_val = (amount_minor / 100.0) if isinstance(amount_minor, (int, float)) else amount_minor
        body = {
            'event_id': f'evt_{int(time.time())}',
            'business_id': bid,
            # use current plan if seeded or fallback to 'free' to avoid invalid_plan errors
            'plan': seeds.get('plan', 'free'),
            'paid_until': (time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time()+86400))),
            'amount': amount_val,
            'currency': 'ZMW',
        }

    # Allow activating a test business so protected endpoints (delivery-locations) succeed
    if method == 'PUT' and path == '/business/{id}':
        body = {
            'is_active': True,
            'name': seeds.get('business_name', 'Test Business'),
        }

    if method == 'POST' and path.endswith('/events/payment_failed'):
        body = {
            'event_id': f'evt_{int(time.time())}',
            'business_id': bid,
            'reason': 'test_failure',
        }

    if method == 'POST' and path.endswith('/notification/send'):
        # best-effort payload for notification proxy (include required `channel`)
        body = {
            'channel': 'in_app',
            'user_id': uid,
            'business_id': bid,
            'template': 'test_notification',
            'payload': {},
        }
        if SERVICE_TOKEN:
            extra_headers['Authorization'] = f'Bearer {SERVICE_TOKEN}'

    if method == 'PUT' and path.endswith('/delivery-locations'):
        body = {'delivery_locations': {'Lusaka': {'price_minor': 2500, 'currency': 'ZMW'}}}
        # delivery locations requires authentication
        # prefer service token but fall back to obtained auth token
        if SERVICE_TOKEN:
            extra_headers['Authorization'] = f'Bearer {SERVICE_TOKEN}'

    return body, extra_headers


def obtain_auth_token():
    headers = {}
    token = None
    # prefer service token if provided
    if SERVICE_TOKEN:
        token = SERVICE_TOKEN
        return token

    if AUTH_USER and AUTH_PASS:
        login_url = urljoin(BASE, '/auth/login')
        body = {'username': AUTH_USER, 'password': AUTH_PASS}
        try:
            resp = http_request('POST', login_url, json_body=body)
            if getattr(resp, 'status_code', 0) in (200, 201):
                try:
                    j = resp.json()
                    token = j.get('access_token') or j.get('token') or j.get('jwt')
                except Exception:
                    token = None
        except Exception:
            token = None

    return token


def call_with_retries(method, url, body=None, headers=None):
    headers = headers or {}
    attempt = 0
    while attempt < RETRY_ATTEMPTS:
        attempt += 1
        resp = http_request(method, url, json_body=body, headers=headers)
        status = getattr(resp, 'status_code', 0)
        # treat 2xx as success
        if 200 <= status < 300:
            return resp
        # for 401/5xx/429/0 we retry
        if status in (0, 401) or 500 <= status < 600 or status == 429:
            backoff = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
            time.sleep(backoff)
            continue
        # other statuses we do not retry
        return resp
    return resp


def main():
    openapi_url = urljoin(BASE, '/openapi.json')
    print(f"Fetching OpenAPI from {openapi_url}")
    try:
        spec_resp = http_get(openapi_url)
        spec = spec_resp.json()
    except Exception as e:
        print("Failed to fetch OpenAPI spec:", e)
        sys.exit(1)

    with open(os.path.join(OUT_DIR, 'openapi.json'), 'w', encoding='utf-8') as f:
        json.dump(spec, f, indent=2)

    token = obtain_auth_token()
    auth_header = {'Authorization': f'Bearer {token}'} if token else {}
    if X_INTERNAL_SECRET:
        auth_header['X-Internal-Secret'] = X_INTERNAL_SECRET
    # Attempt to retrieve a service token for the seeded business if none provided
    runtime_service_token = None
    try:
        if not SERVICE_TOKEN and SEED_IDS.get('business_id'):
            svc_url = urljoin(BASE, f"/auth/service-token/{SEED_IDS.get('business_id')}")
            resp = http_request('POST', svc_url, json_body=None, headers=auth_header)
            if getattr(resp, 'status_code', 0) in (200, 201):
                try:
                    j = resp.json()
                    runtime_service_token = j.get('access_token') or j.get('token') or None
                except Exception:
                    runtime_service_token = None
    except Exception:
        runtime_service_token = None

    # Ensure seeded owner/user and business are active when possible using internal secret
    try:
        internal_secret = os.environ.get('INTERNAL_SERVICE_SECRET') or X_INTERNAL_SECRET
        if internal_secret:
            # activate user if seeded
            user_id = SEED_IDS.get('user_id')
            if user_id:
                try:
                    url = urljoin(BASE, f"/auth/user/{user_id}")
                    headers = {'X-Internal-Secret': internal_secret, 'Content-Type': 'application/json'}
                    _ = http_request('PUT', url, json_body={'is_active': True}, headers=headers)
                except Exception:
                    pass
            # activate business if seeded
            business_id = SEED_IDS.get('business_id') or SEED_IDS.get('id')
            if business_id:
                try:
                    url = urljoin(BASE, f"/business/{business_id}")
                    headers = {'X-Internal-Secret': internal_secret, 'Content-Type': 'application/json'}
                    _ = http_request('PUT', url, json_body={'is_active': True}, headers=headers)
                except Exception:
                    pass
    except Exception:
        pass

    paths = spec.get('paths', {})
    summary = []

    # Build list of operations to call (method, path, op)
    ops = []
    for path, methods in paths.items():
        for method, op in methods.items():
            ops.append((method.upper(), path, op))

    # Priority: run internal / non-destructive endpoints first so they
    # are executed before the generator may run destructive operations
    # (e.g., DELETE /auth/user). This improves reliability for endpoints
    # that depend on freshly-created resources (delivery-locations, outbox).
    def is_priority(method, path):
        if method == 'GET' and path.endswith('/outbox/pending'):
            return True
        if method == 'POST' and path.endswith('/outbox/ack'):
            return True
        if method == 'GET' and path.endswith('/businesses/{business_id}/delivery-locations'):
            return True
        if method == 'PUT' and path.endswith('/businesses/{business_id}/delivery-locations'):
            return True
        if method == 'POST' and path.startswith('/auth/service-token'):
            return True
        if method == 'GET' and path.startswith('/auth/me'):
            return True
        # payment events are safe to run early
        if method == 'POST' and path.endswith('/events/payment_failed'):
            return True
        if method == 'POST' and path.endswith('/events/payment_success'):
            return True
        return False

    def is_destructive(method, path):
        # treat DELETE as destructive; other destructive heuristics can be added
        if method == 'DELETE':
            return True
        # skip any path that explicitly indicates destructive action
        if re.search(r"\bdelete\b|\bdestroy\b", path, flags=re.IGNORECASE):
            return True
        return False

    def is_whitelisted(method, path):
        if not WHITELIST_ONLY:
            return True
        for m, p in DEFAULT_WHITELIST:
            if m != method:
                continue
            # simple containment or prefix match to handle templated paths
            if p in path or path.startswith(p) or path.endswith(p):
                return True
        return False

    called = set()

    def run_op(method_upper, path, op):
        filename = f"{method_upper}_{sanitize_path(path)}.json"
        full_path = path
        full_path = populate_path_with_seeds(full_path)
        url = urljoin(BASE, full_path.lstrip('/'))

        # allow endpoint-specific overrides using seeds
        override_body, override_headers = get_override_for_endpoint(method_upper, path, SEED_IDS)
        if override_body is not None:
            body = override_body
        else:
            body = None
            if 'requestBody' in op:
                content = op['requestBody'].get('content', {})
                if 'application/json' in content:
                    schema = content['application/json'].get('schema', {})
                    body = sample_from_schema(schema)

        print(f"Calling {method_upper} {url} (body={'yes' if body else 'no'})")
        headers = auth_header.copy() if auth_header else {}
        if override_headers:
            headers.update(override_headers)

        # Ensure internal secret present for outbox endpoints if possible
        if (path.endswith('/outbox/pending') or path.endswith('/outbox/ack')) and 'X-Internal-Secret' not in headers:
            if X_INTERNAL_SECRET:
                headers['X-Internal-Secret'] = X_INTERNAL_SECRET
            elif SERVICE_TOKEN:
                headers['X-Internal-Secret'] = SERVICE_TOKEN
            elif runtime_service_token:
                headers['X-Internal-Secret'] = runtime_service_token
                if 'Authorization' not in headers:
                    headers['Authorization'] = f'Bearer {runtime_service_token}'
            elif 'Authorization' in headers:
                auth = headers.get('Authorization')
                if isinstance(auth, str) and auth.lower().startswith('bearer '):
                    headers['X-Internal-Secret'] = auth.split(' ', 1)[1]
                else:
                    headers['X-Internal-Secret'] = auth

        # For business delivery-locations endpoints, prefer using a crafted
        # owner access token (if available) so we don't depend on ephemeral
        # generator-created users. This requires MSME_JWT_SECRET and seeded ids.
        if path.endswith('/businesses/{business_id}/delivery-locations') and 'Authorization' not in headers:
            if MSME_JWT_SECRET and SEED_IDS.get('user_id'):
                try:
                    owner_token = craft_jwt_for_user(SEED_IDS.get('user_id'), SEED_IDS.get('business_id'), MSME_JWT_SECRET)
                    headers['Authorization'] = f'Bearer {owner_token}'
                except Exception:
                    pass

        original_body = body
        try:
            resp = call_with_retries(method_upper, url, body=body, headers=headers)
            status = getattr(resp, 'status_code', 0)
            text = getattr(resp, 'text', '')
            try:
                data = resp.json()
            except Exception:
                data = text
        except Exception as e:
            status = 0
            data = str(e)

        # Special-case fallback for invalid_subscription_plan on subscribe_and_pay
        # Try seeded plan, then 'starter', then 'free' before giving up.
        if method_upper == 'POST' and path.endswith('/subscribe_and_pay'):
            tried = set()
            if isinstance(data, dict) and data.get('detail') == 'invalid_subscription_plan':
                candidates = [SEED_IDS.get('plan'), 'starter', 'free']
                for cand in candidates:
                    if not cand or cand in tried:
                        continue
                    tried.add(cand)
                    alt_body = (original_body or {}).copy()
                    alt_body['plan'] = cand
                    print(f"Retrying subscribe_and_pay with plan={cand}")
                    try:
                        resp2 = call_with_retries(method_upper, url, body=alt_body, headers=headers)
                        status2 = getattr(resp2, 'status_code', 0)
                        try:
                            data2 = resp2.json()
                        except Exception:
                            data2 = getattr(resp2, 'text', '')
                    except Exception as e:
                        status2 = 0
                        data2 = str(e)
                    # accept first non-400 response
                    if not (isinstance(data2, dict) and data2.get('detail') == 'invalid_subscription_plan') and status2 != 400:
                        status = status2
                        data = data2
                        break

        out = {
            'method': method_upper,
            'path': path,
            'url': url,
            'status': status,
            'response': data,
        }
        with open(os.path.join(OUT_DIR, 'responses', filename), 'w', encoding='utf-8') as f:
            json.dump(out, f, indent=2, ensure_ascii=False)

        try:
            if isinstance(data, (dict, list)):
                schema = infer_schema_from_value(data)
                with open(os.path.join(OUT_DIR, 'responses', filename + '.schema.json'), 'w', encoding='utf-8') as f:
                    json.dump(schema, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

        summary.append((method_upper, path, status, filename))
        called.add((method_upper, path))

    # Phase 1: priority ops
    for method_upper, path, op in ops:
        if is_priority(method_upper, path):
            if not is_whitelisted(method_upper, path):
                print(f"Skipping non-whitelisted priority op {method_upper} {path}")
                continue
            if is_destructive(method_upper, path) and not ALLOW_DESTRUCTIVE:
                print(f"Skipping destructive priority op {method_upper} {path}")
                continue
            run_op(method_upper, path, op)

    # Phase 2: run remaining ops
    for method_upper, path, op in ops:
        if (method_upper, path) in called:
            continue
        if not is_whitelisted(method_upper, path):
            print(f"Skipping non-whitelisted op {method_upper} {path}")
            continue
        if is_destructive(method_upper, path) and not ALLOW_DESTRUCTIVE:
            print(f"Skipping destructive op {method_upper} {path}")
            continue
        run_op(method_upper, path, op)

    print("Finished. Saved OpenAPI and responses to", OUT_DIR)
    print("Summary:")
    for m, p, s, fn in summary:
        print(m, p, s, fn)


if __name__ == '__main__':
    main()
