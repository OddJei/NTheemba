"""
SMS/OTP Mock Server - Twilio-compatible API simulation
Port: 5101
Simulates Twilio SMS/WhatsApp and OTP functionality for development.
"""
from flask import Flask, request, jsonify, send_file
import os
import uuid
import json
import random
from datetime import datetime
from pathlib import Path
import threading
import time

ROOT = Path(__file__).parent
LOG_DIR = ROOT / "logs"
CONFIG_FILE = ROOT / "sms_config.json"
LOG_DIR.mkdir(exist_ok=True)

app = Flask(__name__)

# Default config for SMS/OTP simulation
default_config = {
    "twilio_simulation": {
        "delivery_success_rate": 0.95,  # 95% success rate
        "simulate_delays": True,
        "otp_length": 6,
        "otp_expiry_seconds": 300,
        "whatsapp_enabled": True
    },
    "message_templates": {
        "otp": "Your verification code is: {otp}",
        "order_confirmation": "Order {order_id} confirmed. Total: {amount} {currency}",
        "payment_reminder": "Payment pending for order {order_id}: {amount} {currency}"
    },
    "providers": {
        "twilio": {"enabled": True, "simulate_failures": False},
        "360dialog": {"enabled": True, "simulate_failures": False}
    }
}

if not CONFIG_FILE.exists():
    CONFIG_FILE.write_text(json.dumps(default_config, indent=2))

def load_config():
    try:
        return json.loads(CONFIG_FILE.read_text())
    except Exception:
        return default_config

def log_event(kind: str, endpoint: str, body: dict, headers: dict, response: dict = None):
    """Log SMS events for debugging and monitoring."""
    ts = datetime.utcnow().isoformat() + "Z"
    rid = uuid.uuid4().hex
    filename = LOG_DIR / f"sms_events-{datetime.utcnow().date().isoformat()}.jsonl"
    record = {
        "ts": ts,
        "id": rid,
        "kind": kind,
        "endpoint": endpoint,
        "headers": {k: v for k, v in headers.items()},
        "body": body,
        "response": response,
    }
    with open(filename, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")
    return record

# In-memory storage for OTPs and messages
active_otps = {}  # phone -> {"otp": str, "expires_at": datetime, "verified": bool}
sent_messages = []  # List of sent messages for testing

@app.route("/health")
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "service": "SMS/OTP Mock Server",
        "port": 5101,
        "active_otps": len(active_otps),
        "messages_sent": len(sent_messages)
    })

@app.route("/2010-04-01/Accounts/<account_sid>/Messages.json", methods=["POST"])
def twilio_send_message(account_sid):
    """Twilio-compatible SMS/WhatsApp sending endpoint."""
    cfg = load_config()

    # Extract message details
    to = request.form.get('To', '')
    from_number = request.form.get('From', '')
    body = request.form.get('Body', '')

    # Simulate processing delay
    if cfg["twilio_simulation"]["simulate_delays"]:
        time.sleep(random.uniform(0.1, 0.5))

    # Simulate delivery success/failure
    success_rate = cfg["twilio_simulation"]["delivery_success_rate"]
    delivered = random.random() < success_rate

    # Generate response
    message_id = f"SM{random.randint(1000000000, 9999999999)}"
    status = "delivered" if delivered else "failed"

    response_data = {
        "sid": message_id,
        "date_created": datetime.utcnow().isoformat(),
        "date_updated": datetime.utcnow().isoformat(),
        "date_sent": datetime.utcnow().isoformat() if delivered else None,
        "account_sid": account_sid,
        "to": to,
        "from": from_number,
        "body": body,
        "status": status,
        "num_segments": "1",
        "num_media": "0",
        "direction": "outbound-api",
        "api_version": "2010-04-01",
        "price": "-0.00750",
        "price_unit": "USD",
        "uri": f"/2010-04-01/Accounts/{account_sid}/Messages/{message_id}.json"
    }

    # Store message for testing
    sent_messages.append({
        "id": message_id,
        "to": to,
        "from": from_number,
        "body": body,
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
        "provider": "twilio"
    })

    # Keep only last 100 messages
    if len(sent_messages) > 100:
        sent_messages.pop(0)

    log_event("twilio_send", f"/2010-04-01/Accounts/{account_sid}/Messages.json",
              dict(request.form), dict(request.headers), response_data)

    return jsonify(response_data)

@app.route("/v1/messages", methods=["POST"])
def whatsapp_send_message():
    """360Dialog WhatsApp sending endpoint."""
    cfg = load_config()

    payload = request.get_json() or {}
    headers = dict(request.headers)

    # Simulate processing delay
    if cfg["twilio_simulation"]["simulate_delays"]:
        time.sleep(random.uniform(0.2, 0.8))

    # Simulate delivery
    success_rate = cfg["twilio_simulation"]["delivery_success_rate"]
    delivered = random.random() < success_rate

    message_id = f"wamid.{random.randint(100000000000000, 999999999999999)}"
    status = "delivered" if delivered else "failed"

    response_data = {
        "messaging_product": "whatsapp",
        "contacts": [{
            "input": payload.get("to"),
            "wa_id": payload.get("to")
        }],
        "messages": [{
            "id": message_id,
            "message_status": status
        }]
    }

    # Store message for testing
    sent_messages.append({
        "id": message_id,
        "to": payload.get("to"),
        "body": payload.get("text", {}).get("body", ""),
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
        "provider": "360dialog"
    })

    # Keep only last 100 messages
    if len(sent_messages) > 100:
        sent_messages.pop(0)

    log_event("whatsapp_send", "/v1/messages", payload, headers, response_data)

    return jsonify(response_data)

@app.route("/otp/generate", methods=["POST"])
def generate_otp():
    """Generate OTP for phone number."""
    cfg = load_config()
    payload = request.get_json() or {}

    phone = payload.get("phone", "").strip()
    if not phone:
        return jsonify({"success": False, "error": "Phone number required"}), 400

    # Generate OTP
    otp_length = cfg["twilio_simulation"]["otp_length"]
    otp = ''.join([str(random.randint(0, 9)) for _ in range(otp_length)])

    # Set expiry
    expires_at = datetime.utcnow() + timedelta(seconds=cfg["twilio_simulation"]["otp_expiry_seconds"])

    # Store OTP
    active_otps[phone] = {
        "otp": otp,
        "expires_at": expires_at.isoformat(),
        "verified": False,
        "created_at": datetime.utcnow().isoformat()
    }

    # Send OTP via SMS (simulate)
    template = cfg["message_templates"]["otp"]
    message = template.format(otp=otp)

    # Auto-send via mock SMS
    sent_messages.append({
        "id": f"otp_{uuid.uuid4().hex[:8]}",
        "to": phone,
        "body": message,
        "status": "delivered",
        "timestamp": datetime.utcnow().isoformat(),
        "provider": "otp_system"
    })

    log_event("otp_generate", "/otp/generate", payload, dict(request.headers), {
        "phone": phone,
        "otp_sent": True,
        "expires_in": cfg["twilio_simulation"]["otp_expiry_seconds"]
    })

    return jsonify({
        "success": True,
        "phone": phone,
        "message": f"OTP sent to {phone}",
        "expires_in": cfg["twilio_simulation"]["otp_expiry_seconds"]
    })

@app.route("/otp/verify", methods=["POST"])
def verify_otp():
    """Verify OTP for phone number."""
    payload = request.get_json() or {}

    phone = payload.get("phone", "").strip()
    otp_code = payload.get("otp", "").strip()

    if not phone or not otp_code:
        return jsonify({"success": False, "error": "Phone and OTP required"}), 400

    if phone not in active_otps:
        return jsonify({"success": False, "error": "No active OTP for this phone"}), 404

    otp_data = active_otps[phone]

    # Check expiry
    expires_at = datetime.fromisoformat(otp_data["expires_at"])
    if datetime.utcnow() > expires_at:
        del active_otps[phone]
        return jsonify({"success": False, "error": "OTP expired"}), 410

    # Check OTP
    if otp_data["otp"] == otp_code:
        otp_data["verified"] = True
        otp_data["verified_at"] = datetime.utcnow().isoformat()

        log_event("otp_verify", "/otp/verify", payload, dict(request.headers), {
            "phone": phone,
            "verified": True
        })

        return jsonify({
            "success": True,
            "phone": phone,
            "message": "OTP verified successfully"
        })
    else:
        log_event("otp_verify", "/otp/verify", payload, dict(request.headers), {
            "phone": phone,
            "verified": False,
            "error": "Invalid OTP"
        })

        return jsonify({"success": False, "error": "Invalid OTP"}), 400

@app.route("/messages", methods=["GET"])
def get_sent_messages():
    """Get list of sent messages for testing."""
    limit = int(request.args.get('limit', 10))
    messages = sent_messages[-limit:] if sent_messages else []

    return jsonify({
        "messages": messages,
        "total": len(sent_messages),
        "limit": limit
    })

@app.route("/otps", methods=["GET"])
def get_active_otps():
    """Get active OTPs for testing."""
    return jsonify({
        "active_otps": active_otps,
        "count": len(active_otps)
    })

@app.route("/config", methods=["GET", "POST"])
def config():
    """Get or update SMS configuration."""
    if request.method == "GET":
        cfg = load_config()
        return jsonify(cfg)

    data = request.get_json() or {}
    cfg = load_config()
    cfg.update(data)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))

    return jsonify({"success": True, "config": cfg})

@app.route("/logs")
def list_logs():
    """List available log files."""
    files = sorted([p.name for p in LOG_DIR.glob("*.jsonl")])
    return jsonify({"files": files})

@app.route("/logs/<path:name>")
def get_log(name: str):
    """Get specific log file."""
    path = LOG_DIR / name
    if not path.exists():
        return jsonify({"error": "not found"}), 404
    return send_file(str(path), mimetype="text/plain")

@app.route("/reset", methods=["POST"])
def reset():
    """Reset all mock data for testing."""
    global active_otps, sent_messages
    active_otps.clear()
    sent_messages.clear()

    return jsonify({
        "success": True,
        "message": "Mock data reset",
        "active_otps": 0,
        "messages_sent": 0
    })

if __name__ == "__main__":
    print("🚀 SMS/OTP Mock Server starting on port 5101")
    print("📱 Twilio-compatible SMS/WhatsApp API")
    print("🔐 OTP generation and verification")
    print("📊 Logs available at /logs")
    app.run(host="0.0.0.0", port=5101, debug=True)