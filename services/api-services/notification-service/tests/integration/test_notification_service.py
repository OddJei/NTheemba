import asyncio
import pytest

from app.models.schemas import NotificationCreate
from app.services.notification_service import NotificationService
from app.config.settings import settings



import logging
import json


@pytest.mark.asyncio
async def test_create_and_send_notifier_disabled(caplog, monkeypatch):
    # Ensure toggles are disabled at the process level so the service code
    # (which prefers env overrides) picks them up.
    monkeypatch.setenv("NOTIFIER_ENABLED", "0")
    monkeypatch.setenv("AUDIT_ENABLED", "0")

    svc = NotificationService()
    payload = NotificationCreate(user_id='user:42', business_id='biz:1', channel='sms', template='welcome', payload={'phone': '+1234567890', 'message': 'Hello from test'})
    caplog.set_level(logging.INFO)
    res = await svc.create_and_send(payload, metadata={'request_id': 'int-test'})

    # Ensure DB record status updated
    assert getattr(res, 'status', None) == 'notifier_disabled'

    # Inspect captured logs for the NOTIFIER_DISABLED structured message
    found = None
    for rec in caplog.records:
        try:
            m = rec.getMessage()
        except Exception:
            m = getattr(rec, 'message', '')
        if 'NOTIFIER_DISABLED:' in m:
            # message is 'NOTIFIER_DISABLED: <json>'
            try:
                json_part = m.split(':', 1)[1].strip()
                parsed = json.loads(json_part)
                found = parsed
                break
            except Exception:
                continue

    assert found is not None, f"NOTIFIER_DISABLED log not found in logs: {[r.message for r in caplog.records]}"
    assert 'AUDIT_ENABLED' in found
    assert found['AUDIT_ENABLED'] is False
