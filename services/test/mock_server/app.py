"""
Lightweight Flask mock server to simulate messaging and payment providers for local/dev use.
Logs all inbound/outbound events to JSONL files under `logs/`.
Configurable via /config and env variables. Intended for development only.
"""
from flask import Flask, request, jsonify, send_file
import os
import uuid
import json
from datetime import datetime
from pathlib import Path
import threading
import time

ROOT = Path(__file__).parent
LOG_DIR = ROOT / "logs"
CONFIG_FILE = ROOT / "config.json"
LOG_DIR.mkdir(exist_ok=True)

app = Flask(__name__)

# default config
default_config = {
    "forward_targets": {},
    "simulate_delay_ms": 0,
    "next_notify_delivered": True,
    "payment_webhook_delay_ms": 1000,
    "next_payment_outcome": "paid",
}

if not CONFIG_FILE.exists():
    CONFIG_FILE.write_text(json.dumps(default_config, indent=2))


def load_config():
    try:
        return json.loads(CONFIG_FILE.read_text())
    except Exception:
        return default_config


def log_event(kind: str, endpoint: str, body: dict, headers: dict, forward_result: dict | None = None):
    ts = datetime.utcnow().isoformat() + "Z"
    rid = uuid.uuid4().hex
    filename = LOG_DIR / f"events-{datetime.utcnow().date().isoformat()}.jsonl"
    record = {
        "ts": ts,
        "id": rid,
        "kind": kind,
        "endpoint": endpoint,
        "headers": {k: v for k, v in headers.items()},
        "body": body,
        "forward_result": forward_result,
    }
    with open(filename, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")
    return record


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/notify", methods=["POST"])
def notify():
    payload = request.get_json() or {}
    cfg = load_config()
    # simulate delay
    delay = cfg.get("simulate_delay_ms", 0) / 1000.0
    if delay > 0:
        time.sleep(delay)
    rec = log_event("outbound", "/notify", payload, dict(request.headers))
    # optionally forward or simulate delivery
    delivered = cfg.get("next_notify_delivered", True)
    result = {"ok": True, "id": uuid.uuid4().hex, "delivered": delivered}
    rec["forward_result"] = result
    return jsonify(result)


@app.route("/notifications", methods=["POST"])
def notifications():
    payload = request.get_json() or {}
    cfg = load_config()
    # simulate delay
    delay = cfg.get("simulate_delay_ms", 0) / 1000.0
    if delay > 0:
        time.sleep(delay)
    rec = log_event("outbound", "/notifications", payload, dict(request.headers))
    # simulate SMS delivery
    delivered = cfg.get("next_notify_delivered", True)
    result = {"ok": True, "id": uuid.uuid4().hex, "delivered": delivered, "channel": payload.get("channel", "sms")}
    rec["forward_result"] = result
    return jsonify(result)


@app.route("/payment/prompt", methods=["POST"])
def payment_prompt():
    payload = request.get_json() or {}
    cfg = load_config()
    rec = log_event("outbound", "/payment/prompt", payload, dict(request.headers))
    # schedule simulated webhook callback if forwarding target configured
    forward = cfg.get("forward_targets", {}).get("payment_webhook")
    outcome = cfg.get("next_payment_outcome", "paid")
    delay_ms = cfg.get("payment_webhook_delay_ms", 1000)

    def cb():
        time.sleep(delay_ms / 1000.0)
        if forward:
            try:
                import requests
                resp = requests.post(forward, json={"payment_id": payload.get("reference"), "status": outcome, "meta": payload})
                log_event("forward", forward, {"payment_id": payload.get("reference"), "status": outcome}, {}, {"status_code": resp.status_code, "text": resp.text})
            except Exception as e:
                log_event("forward_error", forward, {"error": str(e)}, {}, None)

    if forward:
        threading.Thread(target=cb, daemon=True).start()

    return jsonify({"ok": True, "scheduled_forward": bool(forward)})


@app.route("/inbound/message", methods=["POST"])
def inbound_message():
    payload = request.get_json() or {}
    rec = log_event("inbound", "/inbound/message", payload, dict(request.headers))
    # optionally forward to platform
    cfg = load_config()
    forward_to = cfg.get("forward_targets", {}).get("inbound_message")
    if forward_to:
        try:
            import requests
            resp = requests.post(forward_to, json=payload)
            log_event("forward", forward_to, payload, {}, {"status_code": resp.status_code, "text": resp.text})
            return jsonify({"ok": True, "forwarded": True, "status_code": resp.status_code})
        except Exception as e:
            log_event("forward_error", forward_to, {"error": str(e)}, {}, None)
            return jsonify({"ok": True, "forwarded": False, "error": str(e)})
    return jsonify({"ok": True, "forwarded": False})


@app.route("/inbound/payment_webhook", methods=["POST"])
def inbound_payment_webhook():
    payload = request.get_json() or {}
    rec = log_event("inbound", "/inbound/payment_webhook", payload, dict(request.headers))
    cfg = load_config()
    forward_to = cfg.get("forward_targets", {}).get("payment_webhook")
    if forward_to:
        try:
            import requests
            resp = requests.post(forward_to, json=payload)
            log_event("forward", forward_to, payload, {}, {"status_code": resp.status_code, "text": resp.text})
            return jsonify({"ok": True, "forwarded": True, "status_code": resp.status_code})
        except Exception as e:
            log_event("forward_error", forward_to, {"error": str(e)}, {}, None)
            return jsonify({"ok": True, "forwarded": False, "error": str(e)})
    return jsonify({"ok": True, "forwarded": False})


@app.route("/config", methods=["GET", "POST"])
def config():
    if request.method == "GET":
        cfg = load_config()
        return jsonify(cfg)
    data = request.get_json() or {}
    cfg = load_config()
    cfg.update(data)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
    return jsonify({"ok": True, "config": cfg})


@app.route("/logs")
def list_logs():
    files = sorted([p.name for p in LOG_DIR.glob("*.jsonl")])
    return jsonify({"files": files})


@app.route("/logs/<path:name>")
def get_log(name: str):
    path = LOG_DIR / name
    if not path.exists():
        return jsonify({"error": "not found"}), 404
    return send_file(str(path), mimetype="text/plain")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("MOCK_SERVER_PORT", 5000)), debug=True)
