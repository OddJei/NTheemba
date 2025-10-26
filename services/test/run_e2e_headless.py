"""
Headless end-to-end test harness for NTheemba.

Features:
- Non-interactive (no prompts) — suitable for CI or repeated runs.
- Generates a unique request_id for every message.
- Scenarios: happy_text, unregistered, otp, payment, all
- Options: --repeat, --interval, --timeout, --cleanup, --from, --to, --business-id
- Safe cleanup: only deletes rows that match the test prefix used by this run.

Usage examples:
  python services/test/run_e2e_headless.py --scenario happy_text --repeat 3 --interval 2 --timeout 10 --cleanup

"""
from __future__ import annotations

import argparse
import json
import os
import random
import sqlite3
import string
import sys
import time
import uuid
from datetime import datetime

try:
    import redis
    import requests
except Exception:
    print("Missing dependencies. Install with: pip install redis requests")
    raise


# Config and defaults
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
REDIS_QUEUE_IN = os.environ.get("REDIS_QUEUE_IN", "ntheemba:incoming")
REDIS_QUEUE_OUT = os.environ.get("REDIS_QUEUE_OUT", "ntheemba:outgoing")
DEV_SQLITE_PATH = os.path.abspath(os.environ.get("DEV_SQLITE", "services/ntheemba_api/fixtures/dev.sqlite"))
MOCK_SMS_URL = os.environ.get("MOCK_SMS_URL", "http://localhost:5101")
MOCK_PAYMENT_URL = os.environ.get("MOCK_PAYMENT_URL", "http://localhost:5102")


def make_test_prefix() -> str:
    return f"test-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}-"


TEST_PREFIX = make_test_prefix()


def gen_message_id(tag: str = "m") -> str:
    return f"{TEST_PREFIX}{tag}-{int(time.time() * 1000)}-{random.randint(0, 9999):04d}"


DEFAULT_FROM = os.environ.get("TEST_FROM", "+260952675580")
DEFAULT_BUSINESS_PHONE = os.environ.get("TEST_TO", "business:+1")


# Payloads
def happy_text_payload(from_phone: str, to_phone: str, text: str = "Hi, show catalog") -> dict:
    req = gen_message_id("req")
    return {
        "message_id": gen_message_id("txt"),
        "request_id": req,
        "channel": "whatsapp",
        "from": from_phone,
        "to": to_phone,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "type": "text",
        "text": text,
        "message": text,
        "meta": {"test": "happy_text"},
    }


def unregistered_business_payload() -> dict:
    req = gen_message_id("req")
    return {
        "message_id": gen_message_id("unreg"),
        "request_id": req,
        "channel": "whatsapp",
        "from": "+260999888777",
        "to": "business:+9999",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "type": "text",
        "text": "Hello",
        "message": "Hello",
        "meta": {"test": "unregistered_business"},
    }


def otp_event_payload(sub_type: str = "sent") -> dict:
    correlator = gen_message_id("otp")
    return {
        "message_id": gen_message_id("otp_evt"),
        "event_type": "otp",
        "sub_type": sub_type,
        "otp_code": "%04d" % random.randint(0, 9999),
        "correlator_id": correlator,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


def payment_event_payload(business_id: str | None = None, amount: int = 1000) -> dict:
    return {
        "message_id": gen_message_id("pay_evt"),
        "event_type": "payment",
        "payment_id": gen_message_id("pay"),
        "status": "success",
        "amount": amount,
        "business_id": business_id,
        "correlator_id": gen_message_id("corr"),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# Helpers
def connect_redis() -> "redis.Redis":
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


def push_incoming(r: "redis.Redis", payload: dict) -> None:
    if "request_id" not in payload or not payload.get("request_id"):
        payload["request_id"] = gen_message_id("req")
    raw = json.dumps(payload)
    r.rpush(REDIS_QUEUE_IN, raw)
    print(f"PUSHED -> {REDIS_QUEUE_IN}: message_id={payload.get('message_id')} request_id={payload.get('request_id')}")


def wait_for_outgoing(r: "redis.Redis", request_id: str, timeout: int = 10) -> dict | None:
    end = time.time() + timeout
    while time.time() < end:
        res = r.blpop(REDIS_QUEUE_OUT, timeout=1)
        if res:
            _, raw = res
            try:
                obj = json.loads(raw)
            except Exception:
                obj = raw
            # Match by meta.request_id or in_reply_to referencing our message id
            if isinstance(obj, dict):
                meta = obj.get("meta") or {}
                if meta.get("request_id") == request_id:
                    return obj
                if obj.get("in_reply_to") and request_id in (obj.get("in_reply_to"), meta.get("request_id")):
                    return obj
            # if raw text includes request id
            if isinstance(raw, str) and request_id in raw:
                try:
                    return json.loads(raw)
                except Exception:
                    return {"raw": raw}
    return None


def query_db(sql: str, params: tuple = ()) -> list[dict]:
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


def poll_for_message_row(request_id: str, timeout: int = 10) -> dict | None:
    end = time.time() + timeout
    while time.time() < end:
        rows = query_db("select * from messages where request_id = ?", (request_id,))
        if rows:
            return rows[0]
        time.sleep(0.5)
    return None


def cleanup_db_rows_by_prefix(prefix: str) -> int:
    if not os.path.exists(DEV_SQLITE_PATH):
        return 0
    conn = sqlite3.connect(DEV_SQLITE_PATH)
    try:
        cur = conn.cursor()
        # delete messages and sessions created by this test prefix
        cur.execute("DELETE FROM messages WHERE request_id LIKE ?", (prefix + "%",))
        msgs = cur.rowcount
        cur.execute("DELETE FROM sessions WHERE phone LIKE ?", (prefix + "%",))
        sess = cur.rowcount
        conn.commit()
        return msgs + sess
    finally:
        conn.close()


def run_one_scenario(r: "redis.Redis", scenario: str, opts: argparse.Namespace) -> dict:
    if scenario == "happy_text":
        payload = happy_text_payload(opts.from_phone or DEFAULT_FROM, opts.to_phone or DEFAULT_BUSINESS_PHONE)
        push_incoming(r, payload)
        out = wait_for_outgoing(r, payload["request_id"], timeout=opts.timeout)
        row = poll_for_message_row(payload["request_id"], timeout=opts.timeout)
        ok = bool(out and row)
        return {"payload": payload, "outgoing": out, "row": row, "ok": ok}

    if scenario == "unregistered":
        payload = unregistered_business_payload()
        push_incoming(r, payload)
        out = wait_for_outgoing(r, payload["request_id"], timeout=opts.timeout)
        sessions = query_db("select * from sessions where phone = ?", (payload["from"],))
        ok = len(sessions) >= 1
        return {"payload": payload, "outgoing": out, "sessions": sessions, "ok": ok}

    if scenario == "otp":
        evt = otp_event_payload("sent")
        push_incoming(r, evt)
        sms_ok = False
        try:
            resp = requests.get(MOCK_SMS_URL + "/calls", timeout=1)
            sms_ok = resp.status_code == 200
        except Exception:
            sms_ok = False
        return {"payload": evt, "sms_ok": sms_ok, "ok": sms_ok}

    if scenario == "payment":
        if not opts.business_id:
            return {"ok": False, "error": "--business-id required for payment"}
        evt = payment_event_payload(business_id=opts.business_id)
        push_incoming(r, evt)
        end = time.time() + opts.timeout
        sub = None
        while time.time() < end:
            subs = query_db("select * from subscriptions where business_id = ? order by created_at desc limit 1", (opts.business_id,))
            if subs:
                sub = subs[0]
                break
            time.sleep(0.5)
        ok = bool(sub and sub.get("status") in ("active", "paid"))
        return {"payload": evt, "subscription": sub, "ok": ok}

    return {"ok": False, "error": "unknown scenario"}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--scenario", choices=["happy_text", "unregistered", "otp", "payment", "all"], default="happy_text")
    p.add_argument("--repeat", type=int, default=1, help="How many times to run the scenario")
    p.add_argument("--interval", type=float, default=1.0, help="Seconds between repeats")
    p.add_argument("--timeout", type=int, default=10, help="Per-step timeout seconds")
    p.add_argument("--cleanup", action="store_true", help="Delete test rows created by this run (safe: only prefixes matching this run)")
    p.add_argument("--from", dest="from_phone", default=None)
    p.add_argument("--to", dest="to_phone", default=None)
    p.add_argument("--business-id", dest="business_id", default=None)
    p.add_argument("--interactive", action="store_true", help="Enter interactive chat mode (type messages) - each message gets a unique request_id")
    opts = p.parse_args(argv)

    opts.timeout = int(opts.timeout)

    print("TEST PREFIX:", TEST_PREFIX)

    r = connect_redis()

    results = []
    overall_ok = True
    scenarios = [opts.scenario]
    if opts.scenario == "all":
        scenarios = ["happy_text", "unregistered", "otp"]
        if opts.business_id:
            scenarios.append("payment")

    for i in range(opts.repeat):
        for s in scenarios:
            print(f"RUN {i+1}/{opts.repeat} scenario={s}")
            res = run_one_scenario(r, s, opts)
            results.append({"scenario": s, "iteration": i + 1, "result": res})
            if not res.get("ok"):
                overall_ok = False
            time.sleep(opts.interval)

    # Interactive chat mode: push typed messages with generated request_id and poll for outgoing
    if opts.interactive:
        print("Entering interactive chat mode. Type a line and press Enter to send. Ctrl-C or empty line to exit.")
        try:
            while True:
                line = input("> ")
                if not line:
                    break
                payload = happy_text_payload(opts.from_phone or DEFAULT_FROM, opts.to_phone or DEFAULT_BUSINESS_PHONE, text=line)
                push_incoming(r, payload)
                print("Waiting for reply (timeout", opts.timeout, "s)...")
                out = wait_for_outgoing(r, payload["request_id"], timeout=opts.timeout)
                if out:
                    print("REPLY:", json.dumps(out, indent=2))
                else:
                    print("No reply observed within timeout.")
        except KeyboardInterrupt:
            print("\nInteractive session ended by user.")

    print(json.dumps({"test_prefix": TEST_PREFIX, "overall_ok": overall_ok, "results": results}, default=str, indent=2))

    if opts.cleanup:
        deleted = cleanup_db_rows_by_prefix(TEST_PREFIX)
        print(f"Cleanup: deleted ~{deleted} DB rows matching prefix {TEST_PREFIX}")

    return 0 if overall_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
