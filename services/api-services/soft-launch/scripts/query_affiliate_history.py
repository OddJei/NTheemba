import requests

AFF = "http://localhost:8510"

ids = [
    '6d276375-3132-4757-9c06-1e16e877eeea',
    'e6f4aad5-25c3-467c-ac57-7e0b6f0423f1',
    '2c33f3b2-83c8-492b-8ca5-e8bb66934f0c',
]

for aid in ids:
    try:
        r = requests.get(f"{AFF}/affiliates/{aid}/metrics/history", timeout=10)
        print('\nAFFILIATE', aid, 'STATUS', r.status_code)
        print(r.text)
    except Exception as e:
        print('\nAFFILIATE', aid, 'ERROR', e)
