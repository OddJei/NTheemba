import json
import urllib.request
import urllib.error


def post_json(url: str, payload: dict) -> None:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            print(f"URL: {url}\nSTATUS: {resp.getcode()}\nBODY: {body}\n")
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
        except Exception:
            err_body = ""
        print(f"URL: {url}\nHTTP ERROR: {e.code}\n{err_body}\n")
    except Exception as e:
        print(f"URL: {url}\nERROR: {e}\n")


def main():
    base = "http://localhost:8510"

    payloads = [
        (f"{base}/events/session-cycle-created", {
            "event_id": "test-session-1",
            "event_type": "session_cycle_created",
            "occurred_at": "2026-02-17T12:00:00Z",
            "correlation_id": "test-corr-1",
            "producer": "bot-session",
            "affiliate_id": "aff-test-1",
            "session_id": "sess-test-1",
            "cycle_id": "cycle-1",
            "cycle_state": "started",
            "user_phone": "260971234567",
            "business_id": "biz-1",
            "meta": {"note": "test"},
        }),
        (f"{base}/events/order/delivered", {
            "event_id": "test-order-1",
            "event_type": "order_delivered",
            "occurred_at": "2026-02-17T12:10:00Z",
            "correlation_id": "corr-ord-1",
            "order_id": "order-1",
            "business_id": "biz-1",
            "user_phone": "260971234567",
            "affiliate_id": "aff-test-1",
            "affiliate_code": None,
            "order_amount": 120.5,
            "amount_zmw": 120.5,
            "currency": "ZMW",
            "cycle_id": "cycle-1",
            "meta": {},
        }),
        (f"{base}/callbacks/payments/deposits", {
            "event_type": "payment.callback",
            "event_id": "deposit-test-1",
            "depositId": "deposit-test-1",
            "payment_id": "pay-1",
            "business_id": "biz-1",
            "amount": 150.0,
            "currency": "ZMW",
            "status": "payment_success",
            "method": "pawapay",
        }),
        (f"{base}/events/msme/referral", {
            "event_id": "msme-ref-test-1",
            "deposit_id": "deposit-test-1",
            "affiliate_id": "aff-test-1",
            "business_id": "biz-1",
            "occurred_at": "2026-02-17T12:20:00Z",
        }),
    ]

    for url, payload in payloads:
        print("---")
        post_json(url, payload)


if __name__ == "__main__":
    main()
