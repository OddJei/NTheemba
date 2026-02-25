import requests, json

url = 'http://127.0.0.1:8500/affiliate/onboard'
payload = {
    'profile': {'phone': '+260971000006', 'fullName': 'Seed Affiliate', 'username': 'seedaffiliate', 'email': 'seed-aff@example.com'},
    'preferences': {'channels': ['email'], 'categories': ['promotions']},
    'affiliate_id': 'seed-aff-1'
}

print('POST', url)
try:
    r = requests.post(url, json=payload, timeout=30)
    print('->', r.status_code, r.reason)
    try:
        print(json.dumps(r.json(), indent=2))
    except Exception:
        print(r.text)
except Exception as e:
    print('Request exception:', e)
