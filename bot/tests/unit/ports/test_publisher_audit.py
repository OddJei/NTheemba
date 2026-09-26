"""Tests for outgoing-message and audit contracts."""

from __future__ import annotations

import pytest
from ntheemba.ports.audit import AuditEvent
from ntheemba.ports.publisher import OutgoingMessage, ReplyKind
from tests.fakes.audit import InMemoryAuditSink
from tests.fakes.publisher import InMemoryOutgoingPublisher


@pytest.mark.asyncio
async def test_publisher_preserves_message_order() -> None:
    publisher = InMemoryOutgoingPublisher()
    messages = (
        OutgoingMessage(
            business_id="BUS-1",
            customer_id="260970000001",
            conversation_id="CONV-1",
            ordering_key="CONV-1",
            idempotency_key="MSG-1:1",
            kind=ReplyKind.TEXT,
            text="First",
        ),
        OutgoingMessage(
            business_id="BUS-1",
            customer_id="260970000001",
            conversation_id="CONV-1",
            ordering_key="CONV-1",
            idempotency_key="MSG-1:2",
            kind=ReplyKind.TEXT,
            text="Second",
        ),
    )

    await publisher.publish_many(messages)

    assert [message.text for message in publisher.messages] == ["First", "Second"]


def test_text_message_rejects_image_content() -> None:
    with pytest.raises(ValueError, match="image_url"):
        OutgoingMessage(
            business_id="BUS-1",
            customer_id="260970000001",
            conversation_id="CONV-1",
            ordering_key="CONV-1",
            idempotency_key="MSG-1",
            kind=ReplyKind.TEXT,
            text="Hello",
            image_url="https://example.test/image.jpg",
        )


@pytest.mark.asyncio
async def test_audit_sink_records_structured_event() -> None:
    sink = InMemoryAuditSink()
    event = AuditEvent(
        event_type="intent.proposed",
        request_id="REQ-1",
        business_id="BUS-1",
        conversation_id="CONV-1",
        data={"intent": "start_order"},
    )

    await sink.record(event)

    assert sink.events == [event]
    assert sink.events[0].data["intent"] == "start_order"
