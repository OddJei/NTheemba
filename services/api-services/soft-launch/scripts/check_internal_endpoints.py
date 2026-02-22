import urllib.request
import json

urls = [
    'http://localhost:8500/internal/businesses',
    'http://localhost:8500/internal/affiliates',
]
headers = {'Accept': 'application/json', 'X-Internal-Secret': '0a1b2c3d-4e5f-6789-abcd-ef0123456789'}

for u in urls:
    print('\n---')
    print('URL:', u)
    try:
        req = urllib.request.Request(u, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            status = r.getcode()
            body = r.read().decode(errors='replace')
            print('Status:', status)
            try:
                parsed = json.loads(body)
                print('JSON:', json.dumps(parsed, indent=2)[:800])
            except Exception:
                print('Body (raw):', body[:800])
    except Exception as e:
        print('Request failed:', repr(e))
