#!/usr/bin/env python3
"""Smoke-test bot-session endpoints and write a JSON report.

Tries: /health, /metrics, POST /bot/create, POST /session/create, POST /event/create,
GET /event/{id}, GET /session/{id}, GET /session/{id}/cycles, GET /event/session/{id},
GET /bot/by-phone/{phone}

Writes report to scripts/bot_session_smoke_report.json and prints a short summary.
"""
import json
import sys
import time
from pathlib import Path

BASE = "http://127.0.0.1:8540"
OUT = Path("scripts/bot_session_smoke_report.json")

# lightweight HTTP client with fallbacks
_client = None
_client_name = None

try:
    import httpx

    _client = httpx
    _client_name = "httpx"
except Exception:
    try:
        import requests

        _client = requests
        _client_name = "requests"
    except Exception:
        import urllib.request as _ur
        import urllib.error as _ue
        _client = None
        _client_name = "urllib"


def _get(path, timeout=5):
    url = BASE + path
    try:
        if _client_name == "httpx":
            r = httpx.get(url, timeout=timeout)
            return r.status_code, r.text
        elif _client_name == "requests":
            r = requests.get(url, timeout=timeout)
            return r.status_code, r.text
        else:
            req = _ur.Request(url, method="GET")
            with _ur.urlopen(req, timeout=timeout) as resp:
                return resp.getcode(), resp.read().decode("utf-8")
    except Exception as e:
        return None, str(e)


def _post(path, json_body, timeout=10):
    url = BASE + path
    try:
        if _client_name == "httpx":
            r = httpx.post(url, json=json_body, timeout=timeout)
            return r.status_code, r.text
        elif _client_name == "requests":
            r = requests.post(url, json=json_body, timeout=timeout)
            return r.status_code, r.text
        else:
            data = json.dumps(json_body).encode("utf-8")
            req = _ur.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
            with _ur.urlopen(req, timeout=timeout) as resp:
                return resp.getcode(), resp.read().decode("utf-8")
    except Exception as e:
        return None, str(e)


def safe_json(text):
    try:
        return json.loads(text)
    except Exception:
        return text


def main():
    report = {
        "base": BASE,
        "client": _client_name,
        "timestamp": time.time(),
        "results": [],
    }

    # health
    sc, body = _get("/health")
    report["results"].append({"path": "/health", "status": sc, "body": safe_json(body)})

    # metrics (only check reachable)
    sc, body = _get("/metrics")
    report["results"].append({"path": "/metrics", "status": sc, "body": (body[:1000] + "..." if isinstance(body, str) and len(body) > 1000 else body)})

    # create bot
    bot_payload = {"phone_number": "+260971234567", "type": "custom", "business_id": "business_1"}
    sc, body = _post("/bot/create", bot_payload)
    bot_resp = safe_json(body)
    report["results"].append({"path": "/bot/create", "status": sc, "body": bot_resp})

    bot_id = None
    try:
        if isinstance(bot_resp, dict):
            bot_id = bot_resp.get("bot_id")
    except Exception:
        bot_id = None

    # create session
    session_payload = {"bot_phone": "+260971234567", "user_phone": "+260971234000", "platform": "whatsapp", "business_id": "business_1"}
    sc, body = _post("/session/create", session_payload)
    session_resp = safe_json(body)
    report["results"].append({"path": "/session/create", "status": sc, "body": session_resp})
    session_id = None
    try:
        if isinstance(session_resp, dict):
            session_id = session_resp.get("session_id")
    except Exception:
        session_id = None

    # create event
    event_id = None
    if session_id:
        event_payload = {"session_id": session_id, "event_type": "enter_cart", "user_phone": "+260971234000"}
        sc, body = _post("/event/create", event_payload)
        event_resp = safe_json(body)
        report["results"].append({"path": "/event/create", "status": sc, "body": event_resp})
        try:
            if isinstance(event_resp, dict):
                event_id = event_resp.get("event_id")
        except Exception:
            event_id = None

    # fetch event
    if event_id:
        sc, body = _get(f"/event/{event_id}")
        report["results"].append({"path": f"/event/{event_id}", "status": sc, "body": safe_json(body)})

    # get session
    if session_id:
        sc, body = _get(f"/session/{session_id}")
        report["results"].append({"path": f"/session/{session_id}", "status": sc, "body": safe_json(body)})

        sc, body = _get(f"/session/{session_id}/cycles")
        report["results"].append({"path": f"/session/{session_id}/cycles", "status": sc, "body": safe_json(body)})

        sc, body = _get(f"/event/session/{session_id}")
        report["results"].append({"path": f"/event/session/{session_id}", "status": sc, "body": safe_json(body)})

    # bot by phone
    sc, body = _get("/bot/by-phone/+260971234567")
    report["results"].append({"path": "/bot/by-phone/+260971234567", "status": sc, "body": safe_json(body)})

    # write report
    try:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("WROTE", OUT)
    except Exception as e:
        print("FAILED_WRITE", e)

    # print concise summary
    for r in report["results"]:
        print(f"{r['path']}: status={r['status']}")

    # exit nonzero on any non-2xx for create/critical endpoints
    critical = [p for p in report["results"] if p["path"] in ("/bot/create", "/session/create", "/event/create")]
    for c in critical:
        if not (isinstance(c["status"], int) and 200 <= c["status"] < 300):
            print("SMOKE TEST FAILED:", c["path"], c["status"])
            sys.exit(2)

    print("SMOKE OK")


if __name__ == "__main__":
    main()
