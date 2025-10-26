"""
Payment Mock Server - PrimeNet-compatible API simulation
Port: 5102
Simulates PrimeNet payment gateway for MTN/Airtel/Zamtel mobile money.
"""
from flask import Flask, request, jsonify, send_file
import os
import uuid
import json
import random
from datetime import datetime, timedelta
from pathlib import Path
import threading
import time

ROOT = Path(__file__).parent
LOG_DIR = ROOT / "logs"
CONFIG_FILE = ROOT / "payment_config.json"
LOG_DIR.mkdir(exist_ok=True)

app = Flask(__name__)

# Default config for payment simulation
default_config = {
    "primenet_simulation": {
        "mtn_success_rate": 0.92,      # MTN has highest success rate
        "airtel_success_rate": 0.88,   # Airtel slightly lower
        "zamtel_success_rate": 0.85,   # Zamtel lowest
        "simulate_delays": True,
        "webhook_delay_seconds": 5,
        "auto_complete_payments": True
    },
    "providers": {
        "mtn": {
            "enabled": True,
            "ussd_code": "*170#",
            "name": "MTN Mobile Money",
            "market_share": 0.7
        },
        "airtel": {
            "enabled": True,
            "ussd_code": "*211#",
            "name": "Airtel Money",
            "market_share": 0.25
        },
        "zamtel": {
            "enabled": True,
            "ussd_code": "*255#",
            "name": "Zamtel Kwacha",
            "market_share": 0.05
        }
    },
    "webhook_targets": {},
    "test_accounts": {
        "260971234567": {"balance": 1000.00, "provider": "mtn"},
        "260961234567": {"balance": 500.00, "provider": "airtel"},
        "260951234567": {"balance": 200.00, "provider": "zamtel"}
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
    """Log payment events for debugging and monitoring."""
    ts = datetime.utcnow().isoformat() + "Z"
    rid = uuid.uuid4().hex
    filename = LOG_DIR / f"payment_events-{datetime.utcnow().date().isoformat()}.jsonl"
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

# In-memory storage for payments
active_payments = {}  # transaction_id -> payment data
completed_payments = []  # List of completed payments
test_accounts = {}  # phone -> account data
sent_notifications = []  # List of sent SMS notifications

def initialize_test_accounts():
    """Initialize test accounts with balances."""
    global test_accounts
    cfg = load_config()
    test_accounts = cfg["test_accounts"].copy()

initialize_test_accounts()

@app.route("/health")
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "service": "Payment Mock Server (PrimeNet)",
        "port": 5102,
        "active_payments": len(active_payments),
        "completed_payments": len(completed_payments),
        "providers": ["mtn", "airtel", "zamtel"]
    })

@app.route("/api/v1/payments/initiate", methods=["POST"])
def initiate_payment():
    """PrimeNet-compatible payment initiation endpoint."""
    cfg = load_config()
    payload = request.get_json() or {}

    # Validate required fields
    required_fields = ["amount", "currency", "phone", "provider", "reference"]
    for field in required_fields:
        if field not in payload:
            return jsonify({
                "success": False,
                "error": f"Missing required field: {field}"
            }), 400

    amount = float(payload["amount"])
    currency = payload["currency"]
    phone = payload["phone"]
    provider = payload["provider"].lower()
    reference = payload["reference"]

    # Validate provider
    if provider not in ["mtn", "airtel", "zamtel"]:
        return jsonify({
            "success": False,
            "error": f"Unsupported provider: {provider}. Use: mtn, airtel, zamtel"
        }), 400

    # Validate amount
    if amount <= 0:
        return jsonify({
            "success": False,
            "error": "Amount must be greater than 0"
        }), 400

    # Generate transaction ID
    transaction_id = f"PN_{uuid.uuid4().hex[:12].upper()}"

    # Get provider config
    provider_config = cfg["providers"][provider]

    # Simulate processing delay
    if cfg["primenet_simulation"]["simulate_delays"]:
        time.sleep(random.uniform(0.5, 1.5))

    # Create payment record
    payment_data = {
        "transaction_id": transaction_id,
        "amount": amount,
        "currency": currency,
        "phone": phone,
        "provider": provider,
        "reference": reference,
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "ussd_code": provider_config["ussd_code"],
        "provider_name": provider_config["name"],
        "webhook_url": payload.get("webhook_url"),
        "callback_url": payload.get("callback_url")
    }

    # Store payment
    active_payments[transaction_id] = payment_data

    # Schedule automatic completion if enabled
    if cfg["primenet_simulation"]["auto_complete_payments"]:
        success_rate = cfg["primenet_simulation"][f"{provider}_success_rate"]
        will_succeed = random.random() < success_rate

        def complete_payment_async():
            delay = cfg["primenet_simulation"]["webhook_delay_seconds"]
            time.sleep(delay)

            if will_succeed:
                complete_payment(transaction_id, "success")
            else:
                complete_payment(transaction_id, "failed")

        threading.Thread(target=complete_payment_async, daemon=True).start()

    response_data = {
        "success": True,
        "transaction_id": transaction_id,
        "status": "pending",
        "message": f"Payment initiated. Dial {provider_config['ussd_code']} to complete payment.",
        "ussd_code": provider_config["ussd_code"],
        "provider": provider_config["name"],
        "amount": amount,
        "currency": currency,
        "instructions": f"Please dial {provider_config['ussd_code']} on your {provider_config['name']} phone and authorize the payment of {currency} {amount:.2f}"
    }

    log_event("payment_initiate", "/api/v1/payments/initiate", payload, dict(request.headers), response_data)

    return jsonify(response_data)

@app.route("/api/v1/payments/<transaction_id>", methods=["GET"])
def get_payment_status(transaction_id):
    """Get payment status."""
    if transaction_id in active_payments:
        payment = active_payments[transaction_id].copy()
        # Remove sensitive data
        payment.pop("webhook_url", None)
        payment.pop("callback_url", None)
        return jsonify({"success": True, "payment": payment})

    # Check completed payments
    for payment in completed_payments:
        if payment["transaction_id"] == transaction_id:
            return jsonify({"success": True, "payment": payment})

    return jsonify({"success": False, "error": "Payment not found"}), 404

@app.route("/api/v1/payments/<transaction_id>/complete", methods=["POST"])
def manual_complete_payment(transaction_id):
    """Manually complete a payment (for testing)."""
    payload = request.get_json() or {}
    status = payload.get("status", "success")

    if transaction_id not in active_payments:
        return jsonify({"success": False, "error": "Payment not found"}), 404

    complete_payment(transaction_id, status)
    return jsonify({"success": True, "message": f"Payment {status}"})

def complete_payment(transaction_id: str, status: str):
    """Complete a payment and send webhooks."""
    if transaction_id not in active_payments:
        return

    payment = active_payments[transaction_id]
    cfg = load_config()

    # Update payment status
    payment["status"] = "completed" if status == "success" else "failed"
    payment["updated_at"] = datetime.utcnow().isoformat()
    payment["completed_at"] = datetime.utcnow().isoformat()

    if status == "success":
        payment["confirmation_code"] = f"CONF_{random.randint(100000, 999999)}"
        # Deduct from test account if it exists
        if payment["phone"] in test_accounts:
            test_accounts[payment["phone"]]["balance"] -= payment["amount"]

    # Move to completed payments
    completed_payments.append(payment.copy())
    del active_payments[transaction_id]

    # Keep only last 100 completed payments
    if len(completed_payments) > 100:
        completed_payments.pop(0)

    # Send webhook if configured
    webhook_data = {
        "transaction_id": transaction_id,
        "status": payment["status"],
        "amount": payment["amount"],
        "currency": payment["currency"],
        "phone": payment["phone"],
        "provider": payment["provider"],
        "reference": payment["reference"],
        "completed_at": payment["completed_at"],
        "confirmation_code": payment.get("confirmation_code")
    }

    # Send to configured webhook targets
    for target_name, target_url in cfg["webhook_targets"].items():
        try:
            import requests
            resp = requests.post(target_url, json=webhook_data, timeout=10)
            log_event("webhook_send", target_url, webhook_data, {}, {
                "status_code": resp.status_code,
                "response": resp.text[:200]
            })
        except Exception as e:
            log_event("webhook_error", target_url, webhook_data, {}, {
                "error": str(e)
            })

    # Send to payment's specific webhook/callback URLs
    for url_key in ["webhook_url", "callback_url"]:
        url = payment.get(url_key)
        if url:
            try:
                import requests
                resp = requests.post(url, json=webhook_data, timeout=10)
                log_event("callback_send", url, webhook_data, {}, {
                    "status_code": resp.status_code,
                    "response": resp.text[:200]
                })
            except Exception as e:
                log_event("callback_error", url, webhook_data, {}, {
                    "error": str(e)
                })

    log_event("payment_complete", f"/payments/{transaction_id}/complete", {
        "transaction_id": transaction_id,
        "status": status
    }, {}, webhook_data)

@app.route("/api/v1/accounts/<phone>", methods=["GET"])
def get_account_balance(phone):
    """Get test account balance."""
    if phone in test_accounts:
        return jsonify({
            "success": True,
            "phone": phone,
            "balance": test_accounts[phone]["balance"],
            "provider": test_accounts[phone]["provider"],
            "currency": "ZMW"
        })

    return jsonify({
        "success": False,
        "error": "Account not found",
        "message": f"Test account {phone} not found. Available: {list(test_accounts.keys())}"
    }), 404

@app.route("/api/v1/accounts/<phone>/topup", methods=["POST"])
def topup_account(phone):
    """Add balance to test account."""
    payload = request.get_json() or {}
    amount = float(payload.get("amount", 100.00))

    if phone not in test_accounts:
        return jsonify({"success": False, "error": "Account not found"}), 404

    test_accounts[phone]["balance"] += amount

    return jsonify({
        "success": True,
        "phone": phone,
        "new_balance": test_accounts[phone]["balance"],
        "added": amount
    })

@app.route("/payments", methods=["GET"])
def get_all_payments():
    """Get all payments for testing."""
    limit = int(request.args.get('limit', 20))

    all_payments = list(active_payments.values()) + completed_payments
    all_payments.sort(key=lambda x: x.get('created_at', ''), reverse=True)

    payments = all_payments[:limit]

    return jsonify({
        "payments": payments,
        "total": len(all_payments),
        "active": len(active_payments),
        "completed": len(completed_payments),
        "limit": limit
    })

@app.route("/config", methods=["GET", "POST"])
def config():
    """Get or update payment configuration."""
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
    global active_payments, completed_payments, sent_notifications
    active_payments.clear()
    completed_payments.clear()
    sent_notifications.clear()
    initialize_test_accounts()

    return jsonify({
        "success": True,
        "message": "Mock data reset",
        "active_payments": 0,
        "completed_payments": 0,
        "sent_notifications": 0,
        "test_accounts": len(test_accounts)
    })

@app.route("/stats", methods=["GET"])
def get_stats():
    """Get payment statistics."""
    total_completed = len(completed_payments)
    total_successful = len([p for p in completed_payments if p["status"] == "completed"])
    total_failed = total_completed - total_successful

    provider_stats = {}
    for payment in completed_payments:
        provider = payment["provider"]
        if provider not in provider_stats:
            provider_stats[provider] = {"total": 0, "successful": 0, "failed": 0}
        provider_stats[provider]["total"] += 1
        if payment["status"] == "completed":
            provider_stats[provider]["successful"] += 1
        else:
            provider_stats[provider]["failed"] += 1

    return jsonify({
        "total_payments": len(active_payments) + total_completed,
        "active_payments": len(active_payments),
        "completed_payments": total_completed,
        "successful_payments": total_successful,
        "failed_payments": total_failed,
        "success_rate": total_successful / total_completed if total_completed > 0 else 0,
        "provider_stats": provider_stats
    })

@app.route("/notifications", methods=["POST"])
def send_notification():
    """Send SMS notification (for OTP, etc.)."""
    payload = request.get_json() or {}

    required_fields = ["to", "channel", "message"]
    for field in required_fields:
        if field not in payload:
            return jsonify({"success": False, "error": f"Missing {field}"}), 400

    notification = {
        "id": uuid.uuid4().hex,
        "to": payload["to"],
        "channel": payload["channel"],
        "message": payload["message"],
        "meta": payload.get("meta", {}),
        "sent_at": datetime.utcnow().isoformat(),
        "status": "sent"
    }

    sent_notifications.append(notification)

    # Keep only last 100 notifications
    if len(sent_notifications) > 100:
        sent_notifications.pop(0)

    log_event("notification_send", "/notifications", payload, dict(request.headers), {"id": notification["id"]})

    return jsonify({"success": True, "id": notification["id"]})

@app.route("/notifications", methods=["GET"])
def get_notifications():
    """Get sent notifications for testing."""
    limit = int(request.args.get('limit', 20))
    notifications = sent_notifications[-limit:]
    return jsonify({
        "notifications": notifications,
        "total": len(sent_notifications),
        "limit": limit
    })

if __name__ == "__main__":
    print("💰 Payment Mock Server starting on port 5102")
    print("📱 PrimeNet-compatible API for MTN/Airtel/Zamtel")
    print("🔄 Automatic payment completion simulation")
    print("📊 Test accounts available: 260971234567 (MTN), 260961234567 (Airtel), 260951234567 (Zamtel)")
    print("📋 Stats available at /stats")
    app.run(host="0.0.0.0", port=5102, debug=True)