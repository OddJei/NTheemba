import requests, json

url = 'http://127.0.0.1:8500/msme/onboard'
payload = {
    'profile': {'phone': '+260971000007', 'fullName': 'Seed MSME', 'username': 'seedmsme', 'email': 'seed-msme@example.com'},
    'business': {'businessName': 'Seed Business Ltd', 'phone': '+260971000010', 'location': 'Lusaka'},
    'products': [{'name': 'Seed Product', 'price': '1000', 'initialStock': '10'}]
}

print('POST', url)
try:
    r = requests.post(url, json=payload, timeout=60)
    print('->', r.status_code, r.reason)
    try:
        print(json.dumps(r.json(), indent=2))
    except Exception:
        print(r.text)
except Exception as e:
    print('Request exception:', e)
