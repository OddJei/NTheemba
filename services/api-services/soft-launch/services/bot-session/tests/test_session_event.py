import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


_db_file = Path(tempfile.gettempdir()) / f"bot_session_test_{uuid.uuid4().hex}.db"
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_db_file.as_posix()}")
os.environ.setdefault("DISABLE_CLEANUP_JOBS", "1")

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from app.main import app


@pytest.fixture(autouse=True)
def msme_stubs(monkeypatch):
    # stub msme auth lookup
    async def fake_auth(phone):
        # treat phones ending with 0 as msme, ending with 1 as staff
        if phone.endswith("0"):
            return {"user_id": "uid-msme", "role": "msme", "business_id": "biz-123"}
        if phone.endswith("1"):
            return {"user_id": "uid-staff", "role": "staff", "business_id": "biz-123"}
        return None

    monkeypatch.setattr("app.main._msme_auth_lookup", fake_auth)

    async def fake_publish(*args, **kwargs):
        return True

    monkeypatch.setattr("app.main.event_publisher.publish_business_event", fake_publish)


def test_session_upsert_and_event_flow():
    with TestClient(app) as client:
        phone = f"+260700{uuid.uuid4().hex[:9]}"
        # create bot
        r = client.post("/bot/create", json={"phone_number": phone, "type": "default", "business_id": None})
        assert r.status_code == 200
        bot_id = r.json()["bot_id"]

        # create session
        r = client.post("/session/create", json={"user_phone": phone, "bot_id": bot_id, "platform": "wa"})
        assert r.status_code == 200
        sess = r.json()
        assert sess["session_mode"] in ("public", "registered")

        # create first event
        r = client.post(
            "/event/create",
            json={"session_id": sess["session_id"], "bot_id": bot_id, "payload_events": {"inbound": {"message": "hi"}}},
        )
        assert r.status_code == 200
        e1 = r.json()
        assert e1["message_count"] == 1

        # create second event referencing first
        r = client.post(
            "/event/create",
            json={
                "session_id": sess["session_id"],
                "bot_id": bot_id,
                "last_event_id": e1["event_id"],
                "payload_events": {"inbound": {"message": "hello again"}},
            },
        )
        assert r.status_code == 200
        e2 = r.json()
        assert e2["message_count"] == 2
