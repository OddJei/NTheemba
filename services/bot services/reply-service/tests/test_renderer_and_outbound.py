import json

import pytest

from app.core.config import get_settings
from app.models import ReplyRequest
from app.services.renderer import ReplyRenderer
from app.workers.queue_listener import _normalize_reply_request, _parse_stream_payload


@pytest.mark.asyncio
async def test_renderer_prefix_defaults():
    settings = get_settings()
    rr = ReplyRequest(event_id="evt1", session_id="sess1", text="hello", meta={"business_name": "Kitwe Solar"})
    r = ReplyRenderer(settings)
    out = await r.render_text(rr)
    assert "NTheemba" in out
    assert "Kitwe Solar" in out


def test_parse_stream_payload_merges_flat_fields():
    msg = {
        "event_id": "evt1",
        "session_id": "sess1",
        "next_node": "help",
        "payload": json.dumps({"text": "hi"}),
        "trace_id": "t1",
    }
    obj = _parse_stream_payload(msg)
    assert obj["text"] == "hi"
    assert obj["event_id"] == "evt1"
    assert obj["trace_id"] == "t1"


def test_normalize_reply_request_reads_text():
    obj = {"event_id": "evt1", "session_id": "sess1", "text": "hello"}
    rr = _normalize_reply_request(obj)
    assert rr.text == "hello"
