import time
import requests
import uuid
import statistics

AFF_URL = "http://localhost:8510/events/order/delivered"

def send_event(affiliate_id=None, business_id=None, order_id=None):
    payload = {
        "event_id": str(uuid.uuid4()),
        "order_id": order_id or f"order-{uuid.uuid4()}",
        "affiliate_id": affiliate_id,
        "business_id": business_id,
        "amount_zmw": 100.0,
        "occurred_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    start = time.time()
    r = requests.post(AFF_URL, json=payload, timeout=5)
    latency = time.time() - start
    return r.status_code, latency, r.text

if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--count', type=int, default=50)
    p.add_argument('--affiliate-id')
    p.add_argument('--business-id')
    args = p.parse_args()

    latencies = []
    successes = 0
    for i in range(args.count):
        status, latency, text = send_event(affiliate_id=args.affiliate_id, business_id=args.business_id)
        latencies.append(latency)
        if 200 <= status < 300:
            successes += 1
        print(f"{i+1}/{args.count}: status={status} latency={latency:.3f}s")
    print("\nSummary:")
    print(f"Sent: {args.count}  Successes: {successes}")
    print(f"Min: {min(latencies):.3f}s  Max: {max(latencies):.3f}s  Mean: {statistics.mean(latencies):.3f}s  p95: {statistics.quantiles(latencies, n=100)[94]:.3f}s")
