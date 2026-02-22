import requests
import json

BASE = "http://localhost:8590"

headers = {"content-type": "application/json"}
auth_headers = {"content-type": "application/json", "Authorization": "Bearer dummy"}

# Minimal deposit initiate payload — adjust fields to match service expectations
deposit_payload = {
    "order_id": "test-order-zmw-1",
    "amount_minor": 1000,
    "currency": "ZMW",
    "initiator_id": "order-delivery",
    "initiator_role": "service",
    "payment_type": "oneoff",
    "msme_net_minor": 900,
    "phoneNumber": "+260971000000"
}

payout_payload = {
    "order_id": "test-order-zmw-1",
    "amount_minor": 900,
    "currency": "ZMW",
    "initiator_id": "order-delivery",
    "initiator_role": "service",
    "settlement_id": "test-settlement-zmw-1",
    "phoneNumber": "+260971000000"
}

refund_payload = {
    "order_id": "test-order-zmw-1",
    "deposit_id": "test-deposit-zmw-1",
    "amount_minor": 1000,
    "currency": "ZMW",
    "initiator_id": "order-delivery",
    "initiator_role": "service",
    "phoneNumber": "+260971000000"
}


def post(path, payload, use_auth=False):
    url = BASE + path
    h = auth_headers if use_auth else headers
    try:
        r = requests.post(url, headers=h, data=json.dumps(payload), timeout=10)
        print(url, r.status_code)
        try:
            print(r.json())
        except Exception:
            print(r.text)
    except Exception as e:
        print("ERROR", url, e)


if __name__ == '__main__':
    print("Posting deposit initiate")
    post("/pawapay/deposits/initiate", deposit_payload)
    print("Posting payout initiate")
    post("/pawapay/payouts/initiate", payout_payload)
    print("Posting refund initiate")
    post("/pawapay/refunds/initiate", refund_payload, use_auth=True)
