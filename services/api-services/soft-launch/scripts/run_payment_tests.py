import json
import urllib.request

def post(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except Exception as e:
        return None, str(e)

base = 'http://127.0.0.1:8590'

print('POST deposit')
status, body = post(base + '/pawapay/deposits/initiate', {"amountMinor":1000, "currency":"ZAR", "orderId":"test-order-123", "paymentType":"purchase"})
print(status)
print(body)

print('\nPOST payout')
status, body = post(base + '/pawapay/payouts/initiate', {"amountMinor":800, "currency":"ZAR", "orderId":"test-order-123", "destination":{"bankAccount":"123456"}})
print(status)
print(body)

print('\nPOST refund')
status, body = post(base + '/pawapay/refunds/initiate', {"amountMinor":500, "currency":"ZAR", "orderId":"test-order-123", "depositId": null})
print(status)
print(body)
