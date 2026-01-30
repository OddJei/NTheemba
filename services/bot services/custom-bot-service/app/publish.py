from __future__ import annotations

import json
import os
from typing import Any


REPLY_STREAM = os.getenv("CUSTOM_BOT_REPLY_STREAM", "reply:requests")
AUDIT_STREAM = os.getenv("CUSTOM_BOT_AUDIT_STREAM", "oob:audit")


async def publish_reply_request(
    r,
    *,
    event_id: str | None,
    session_id: str | None,
    text: str,
    next_node: str,
    oob_ref: str | None,
    meta: dict[str, Any] | None = None,
    trace_id: str | None = None,
    span_id: str | None = None,
) -> str:
    payload = {
        "event_id": event_id,
        "session_id": session_id,
        "next_node": next_node,
        "text": text,
        "refs": {"oob": oob_ref} if oob_ref else {},
        "meta": meta or {},
    }
    # propagate trace context into payload for downstream correlation
    if trace_id:
        payload["trace_id"] = trace_id
    if span_id:
        payload["span_id"] = span_id
    # Keep stream fields flat and small; store full payload as JSON too.
    return await r.xadd(
        REPLY_STREAM,
        {
            "event_id": event_id or "",
            "session_id": session_id or "",
            "next_node": next_node,
            "payload": json.dumps(payload),
            "trace_id": trace_id or "",
            "span_id": span_id or "",
        },
    )


async def publish_audit(
    r,
    *,
    event_id: str | None,
    session_id: str | None,
    intent_ids: list[str],
    result: dict[str, Any],
    trace_id: str | None = None,
    span_id: str | None = None,
) -> str:
    payload = {
        "event_id": event_id,
        "session_id": session_id,
        "intent_ids": intent_ids,
        "result": result,
    }
    if trace_id:
        payload["trace_id"] = trace_id
    if span_id:
        payload["span_id"] = span_id
    return await r.xadd(
        AUDIT_STREAM,
        {
            "event_id": event_id or "",
            "session_id": session_id or "",
            "payload": json.dumps(payload),
            "trace_id": trace_id or "",
            "span_id": span_id or "",
        },
    )
