from __future__ import annotations

from ntheemba.observability import (
    bind_trace_context,
    current_trace_context,
    new_trace_context,
)


def test_context_binding_restores_previous_context() -> None:
    root = new_trace_context(request_id="req-1", business_id="business-1")

    assert current_trace_context() is None
    with bind_trace_context(root):
        assert current_trace_context() is root
    assert current_trace_context() is None


def test_child_context_preserves_correlation_and_sets_parent() -> None:
    root = new_trace_context(
        request_id="req-1",
        business_id="business-1",
        conversation_id="conversation-1",
        message_id="message-1",
        attributes={"environment": "test"},
    )

    child = root.child(attributes={"workflow": "booking"})

    assert child.trace_id == root.trace_id
    assert child.span_id != root.span_id
    assert child.parent_span_id == root.span_id
    assert child.request_id == "req-1"
    assert child.business_id == "business-1"
    assert child.conversation_id == "conversation-1"
    assert child.message_id == "message-1"
    assert child.attributes == {"environment": "test", "workflow": "booking"}
