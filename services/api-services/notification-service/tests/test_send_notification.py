from fastapi.testclient import TestClient
from app.config import settings

# Ensure tests for the HTTP endpoints run with notifier/audit enabled so
# behavior is deterministic even if the outer shell environment differs.
settings.AUDIT_ENABLED = True
settings.NOTIFIER_ENABLED = True

from app.main import app


client = TestClient(app)


def test_send_notification_missing_phone():
    payload = {
        "channel": "sms",
        "payload": {"message": "hi"}
    }
    r = client.post("/notification/send", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "failed"
    assert "missing phone" in (data.get("error_message") or "")


def test_send_notification_email_success():
    payload = {
        "channel": "email",
        "payload": {"email": "test@example.com", "message": "hello"}
    }
    r = client.post("/notification/send", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "sent"
