"""
Lightweight end-to-end test harness for NTheemba.

- Publishes canonical messages to the incoming Redis list (uses rpush).
- Waits for replies on the outgoing Redis list (blpop with timeout).
- Polls the dev sqlite DB for expected rows.
- Optionally checks mock HTTP endpoints.

Usage: python services/test/run_e2e.py --scenario happy_text

This script is intentionally minimal and safe to run against a local dev environment.
"""
import argparse
import json
import os
import random
import sqlite3
import string
import sys
import time
from datetime import datetime

try:
    import redis
    import requests
except Exception as e:
    print("Missing dependencies. Install with: pip install redis requests")
    raise

# Defaults tuned to repo conventions
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
REDIS_QUEUE_IN = os.environ.get("REDIS_QUEUE_IN", "ntheemba:incoming")
REDIS_QUEUE_OUT = os.environ.get("REDIS_QUEUE_OUT", "ntheemba:outgoing")
DEV_SQLITE_PATH = os.path.abspath(os.environ.get("DEV_SQLITE", "services/ntheemba_api/fixtures/dev.sqlite"))
MOCK_SMS_URL = os.environ.get("MOCK_SMS_URL", "http://localhost:5101")
MOCK_PAYMENT_URL = os.environ.get("MOCK_PAYMENT_URL", "http://localhost:5102")

TEST_PREFIX = datetime.utcnow().strftime("test-%Y%m%d%H%M%S-") + ("%04d" % random.randint(0, 9999))

DEFAULT_FROM = "+260952675580"
DEFAULT_BUSINESS_PHONE = "business:+1"

# Canonical payload factories

def gen_message_id(tag="m"):
    return f"{TEST_PREFIX}{tag}-{int(time.time()*1000)}-{random.randint(0,9999):04d}"


def happy_text_payload():
    text = "Hi, show catalog"
    req = gen_message_id("req")
    return {
        "message_id": gen_message_id("txt"),
        "request_id": req,
        "channel": "whatsapp",
        "from": DEFAULT_FROM,
        "to": DEFAULT_BUSINESS_PHONE,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "type": "text",
        "text": text,
        # validator expects 'message' and 'meta' keys
        "message": text,
        "meta": {"test": "happy_text"},
    }


def unregistered_business_payload():
    text = "Hello"
    req = gen_message_id("req")
    return {
        "message_id": gen_message_id("unreg"),
        "request_id": req,
        "channel": "whatsapp",
        "from": "+260999888777",
        "to": "business:+9999",  # non-existing
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "type": "text",
        "text": text,
        "message": text,
        "meta": {"test": "unregistered_business"},
    }


def expired_subscription_payload(business_id):
    text = "Hi"
    req = gen_message_id("req")
    return {
        "message_id": gen_message_id("expired"),
        "request_id": req,
        "channel": "whatsapp",
        "from": "+260111222333",
        "to": f"business:{business_id}",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "type": "text",
        "text": text,
        "message": text,
        "meta": {"test": "expired_subscription"},
    }


def otp_event_payload(sub_type="sent", correlator=None):
    correlator = correlator or gen_message_id("otp")
    return {
        "message_id": gen_message_id("otp_evt"),
        "event_type": "otp",
        "sub_type": sub_type,
        "otp_code": "%04d" % random.randint(0, 9999),
        "correlator_id": correlator,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


def payment_event_payload(status="success", business_id=None, amount=1000):
    return {
        "message_id": gen_message_id("pay_evt"),
        "event_type": "payment",
        "payment_id": gen_message_id("pay"),
        "status": status,
        "amount": amount,
        "business_id": business_id,
        "correlator_id": gen_message_id("corr"),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# Helpers

def connect_redis():
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


def push_incoming(r, payload):
    # Ensure every pushed payload has a request_id so the system can trace
    # and tests can reliably poll for processing results.
    if "request_id" not in payload or not payload.get("request_id"):
        payload["request_id"] = gen_message_id("req")
    raw = json.dumps(payload)
    r.rpush(REDIS_QUEUE_IN, raw)
    print(f"Pushed to {REDIS_QUEUE_IN}: {payload.get('message_id')} (request_id={payload.get('request_id')})")


def wait_for_outgoing(r, match_fn=None, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        res = r.blpop(REDIS_QUEUE_OUT, timeout=1)
        if res:
            q, raw = res
            try:
                obj = json.loads(raw)
            except Exception:
                obj = raw
            print("Dequeued outgoing:", obj)
            if not match_fn or match_fn(obj):
                return obj
    return None


def query_db(sql, params=()):
    if not os.path.exists(DEV_SQLITE_PATH):
        print("DEV sqlite not found at", DEV_SQLITE_PATH)
        return []
    conn = sqlite3.connect(DEV_SQLITE_PATH)
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        cols = [c[0] for c in cur.description] if cur.description else []
        return [dict(zip(cols, r)) for r in rows]
    finally:
        conn.close()


def poll_for_message_row(message_id, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        rows = query_db("select * from messages where message_id = ?", (message_id,))
        if rows:
            return rows[0]
        time.sleep(0.5)
    return None


# Scenarios

def run_happy_text(r):
    payload = happy_text_payload()
    push_incoming(r, payload)
    # outgoing events vary in shape; match either explicit in_reply_to or
    # meta.request_id referencing our request_id. Fall back to polling the DB
    # for a message created by this request.
    def match_out(o):
        try:
            if isinstance(o, dict):
                if o.get("in_reply_to") == payload["message_id"]:
                    return True
                meta = o.get("meta") or {}
                if meta.get("request_id") == payload["request_id"]:
                    return True
        except Exception:
            return False
        return False

    out = wait_for_outgoing(r, match_out, timeout=8)
    # DB messages use message_id; if not written use request_id fallback
    msg_row = poll_for_message_row(payload["message_id"], timeout=4)
    if not msg_row:
        # try to find message by request_id
        rows = query_db("select * from messages where request_id = ?", (payload["request_id"],))
        msg_row = rows[0] if rows else None
    ok = bool(out and msg_row)
    print("Happy text result:", "PASS" if ok else "FAIL")
    return {"outgoing": out, "message_row": msg_row, "ok": ok}


def run_unregistered_business(r):
    payload = unregistered_business_payload()
    push_incoming(r, payload)
    # Expect session created without business association
    out = wait_for_outgoing(r, timeout=5)
    rows = query_db("select * from sessions where phone = ?", (payload["from"],))
    ok = len(rows) >= 1
    print("Unregistered business result:", "PASS" if ok else "FAIL")
    return {"outgoing": out, "sessions": rows, "ok": ok}


def run_otp_flow(r):
    evt = otp_event_payload("sent")
    push_incoming(r, evt)
    # Check mock SMS server if reachable
    sms_ok = False
    try:
        resp = requests.get(MOCK_SMS_URL + "/calls", timeout=1)
        if resp.status_code == 200:
            sms_ok = True
    except Exception:
        pass
    print("OTP send observed in mock SMS:", sms_ok)
    return {"sms_ok": sms_ok}


def run_payment_event(r, business_id):
    evt = payment_event_payload("success", business_id=business_id)
    push_incoming(r, evt)
    # Poll subscription row for the business
    end = time.time() + 10
    sub = None
    while time.time() < end:
        subs = query_db("select * from subscriptions where business_id = ? order by created_at desc limit 1", (business_id,))
        if subs:
            sub = subs[0]
            break
        time.sleep(0.5)
    ok = bool(sub and sub.get("status") in ("active", "paid"))
    print("Payment event result:", "PASS" if ok else "FAIL")
    return {"subscription": sub, "ok": ok}


# CLI and orchestration

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=["happy_text", "unregistered", "otp", "payment", "all"], default="happy_text")
    parser.add_argument("--business-id", default=None)
    args = parser.parse_args()

    r = connect_redis()

    if args.scenario == "happy_text":
        res = run_happy_text(r)
    elif args.scenario == "unregistered":
        res = run_unregistered_business(r)
    elif args.scenario == "otp":
        res = run_otp_flow(r)
    elif args.scenario == "payment":
        if not args.business_id:
            print("--business-id required for payment scenario")
            sys.exit(2)
        res = run_payment_event(r, args.business_id)
    elif args.scenario == "all":
        out = {}
        out['happy'] = run_happy_text(r)
        out['unregistered'] = run_unregistered_business(r)
        out['otp'] = run_otp_flow(r)
        if args.business_id:
            out['payment'] = run_payment_event(r, args.business_id)
        res = out
    print(json.dumps(res, default=str, indent=2))


if __name__ == "__main__":
    main()
