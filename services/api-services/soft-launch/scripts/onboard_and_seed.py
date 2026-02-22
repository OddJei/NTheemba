#!/usr/bin/env python3
"""Onboard a user and business on msme-engine and re-run contract generation with seeds.

Creates a user via `/auth/register`, creates a business via `/business/register` linking
the user, then runs `generate_contracts_msme.py` with `CONTRACT_SEED_IDS` set to the
created IDs so downstream endpoint calls use valid IDs.

Usage:
  python scripts/onboard_and_seed.py
Environment:
  MSME_BASE_URL - base URL (default http://localhost:8500)
  (optional) CONTRACT_RETRY_ATTEMPTS etc are respected by the generator.
"""
import json
import os
import subprocess
import sys
import time
from urllib.parse import urljoin

try:
    import requests
except Exception:
    requests = None

BASE = os.environ.get('MSME_BASE_URL', 'http://localhost:8500')


def http_request(method, path, json_body=None, headers=None):
    url = urljoin(BASE, path)
    headers = headers or {}
    if requests:
        fn = getattr(requests, method.lower())
        return fn(url, json=json_body, headers=headers, timeout=10)
    import urllib.request
    data = None
    req_headers = headers.copy()
    if json_body is not None:
        data = json.dumps(json_body).encode('utf-8')
        req_headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, method=method.upper(), headers=req_headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        class R:
            status_code = resp.getcode()
            headers = dict(resp.getheaders())
            text = resp.read().decode('utf-8')
            def json(self):
                return json.loads(self.text)
        return R()


def register_user():
    import random, string
    suffix = ''.join(random.choice(string.ascii_lowercase+string.digits) for _ in range(6))
    username = f'testuser_{suffix}'
    email = f'{username}@example.com'
    password = 'ChangeMe1!'
    body = {'username': username, 'email': email, 'password': password}
    print('Registering user', username)
    resp = http_request('POST', '/auth/register', json_body=body)
    if getattr(resp, 'status_code', 0) >= 400:
        print('User registration failed:', resp.status_code, getattr(resp, 'text', ''))
        return None
    j = resp.json()
    user_id = j.get('id') or j.get('user', {}).get('id')
    print('Registered user id:', user_id)
    # return username and password for login flows
    return {'id': user_id, 'username': username, 'password': password, 'email': email}


def register_business(user_id):
    import random
    name = f'Test Business {int(time.time()) % 10000}'
    body = {'name': name, 'owner_user_id': user_id}
    print('Registering business', name)
    resp = http_request('POST', '/business/register', json_body=body)
    if getattr(resp, 'status_code', 0) >= 400:
        print('Business registration failed:', resp.status_code, getattr(resp, 'text', ''))
        return None
    j = resp.json()
    # BusinessRegisterOut: { business: { id: ... }, msme_code: ... }
    business = j.get('business') or j
    business_id = business.get('id')
    msme_code = j.get('msme_code')
    print('Registered business id:', business_id, 'msme_code:', msme_code)
    return {'id': business_id, 'msme_code': msme_code}


def run_generator_with_seeds(user_id, business_id):
    seeds = {'user_id': user_id, 'business_id': business_id, 'id': business_id}
    env = os.environ.copy()
    env['CONTRACT_SEED_IDS'] = json.dumps(seeds)
    # include a sensible internal secret default so outbox/ack can be tested
    env['X_INTERNAL_SECRET'] = env.get('X_INTERNAL_SECRET', 'secret')
    print('Running contract generator with seeds:', seeds)
    subprocess.check_call([sys.executable, 'scripts/generate_contracts_msme.py'], env=env)


def main():
    user = register_user()
    if not user:
        print('Aborting: could not register user')
        sys.exit(1)
    user_id = user['id']
    business = register_business(user_id)
    if not business:
        print('Aborting: could not register business')
        sys.exit(1)
    business_id = business['id']

    # attempt login to obtain an access token for authenticated endpoints
    login_body = {'identifier': user['username'], 'password': user['password']}
    try:
        resp = http_request('POST', '/auth/login', json_body=login_body)
        token = None
        if getattr(resp, 'status_code', 0) in (200, 201):
            j = resp.json()
            token = j.get('access_token') or j.get('token') or j.get('jwt') or j.get('accessToken')
        if token:
            os.environ['MSME_SERVICE_TOKEN'] = token
            print('Obtained access token; passing to generator')
    except Exception:
        pass

    seeds = {'user_id': user_id, 'business_id': business_id, 'id': business_id}
    # include msme_code if available
    if business.get('msme_code'):
        seeds['msme_code'] = business.get('msme_code')
    # include placeholder phone and deposit/payment ids
    seeds.setdefault('phone_number', user.get('email'))
    seeds.setdefault('payment_id', 'pay_test_123')
    seeds.setdefault('depositId', 'dep_test_123')

    env = os.environ.copy()
    env['CONTRACT_SEED_IDS'] = json.dumps(seeds)
    env['CONTRACT_RETRY_ATTEMPTS'] = env.get('CONTRACT_RETRY_ATTEMPTS', '2')
    env['X_INTERNAL_SECRET'] = env.get('X_INTERNAL_SECRET', 'secret')
    print('Running contract generator with seeds:', seeds)
    subprocess.check_call([sys.executable, 'scripts/generate_contracts_msme.py'], env=env)


if __name__ == '__main__':
    main()
