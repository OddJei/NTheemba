Mock Server (Flask) for local development

This mock server simulates messaging and payment providers for development and testing.
It logs every inbound/outbound event to JSONL files in `logs/` and can forward simulated inbound events to your platform webhooks.

How to run

# 1) Install deps (prefer venv)
python -m venv .venv
. .venv\Scripts\Activate; pip install flask requests

# 2) Run
. .venv\Scripts\Activate; python app.py

Default port: 5000

Basic endpoints
- GET /health
- POST /notify            -> simulate sending a message
- POST /payment/prompt    -> simulate sending a payment prompt and optionally forward a webhook
- POST /inbound/message   -> simulate an inbound message (seller/customer)
- POST /inbound/payment_webhook -> simulate a payment provider webhook inbound to platform
- GET/POST /config        -> read/update behavior (forward targets, delays, next outcomes)
- GET /logs               -> list logs
- GET /logs/<name>        -> download log file

How to forward to your platform
1. Start your platform locally (e.g., FastAPI) and note the webhook endpoints (/payments/{id}/webhook, /webhooks/whatsapp_confirm).
2. Call POST /config with JSON:
{
  "forward_targets": {
    "payment_webhook": "http://localhost:8000/payments/<payment_id>/webhook",
    "inbound_message": "http://localhost:8000/webhooks/whatsapp_confirm"
  },
  "payment_webhook_delay_ms": 1500,
  "next_payment_outcome": "paid"
}

Now when /payment/prompt is called, the mock server will forward a simulated webhook to the configured platform URL after the configured delay.

Logs
All logs are stored under `logs/` as JSONL files named events-YYYY-MM-DD.jsonl. Each line is a JSON object with keys { ts, id, kind, endpoint, headers, body, forward_result }.

Security
This server is for development only. Do not expose to public networks. It does not store or forward real secrets or payment pins.
