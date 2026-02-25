import requests, json
r = requests.get('http://127.0.0.1:8570/outbox/pending', headers={'X-Internal-Secret':'test-internal-secret'})
print(r.status_code)
print(r.text)
