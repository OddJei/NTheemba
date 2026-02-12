from __future__ import annotations

import argparse
import asyncio
import json
import time
import uuid
from typing import Any, Dict, Optional

from redis.asyncio import Redis


def _now_ms() -> int:
    return int(time.time() * 1000)


async def _publish_request(redis: Redis, *, stream: str, payload: Dict[str, Any]) -> str:
    return await redis.xadd(stream, {"payload": json.dumps(payload)})


async def _read_receipts(
    redis: Redis,
    *,
    stream: str,
    timeout_seconds: float,
    stop_after: int,
) -> None:
    last_id = "0-0"
    found = 0
    deadline = time.time() + timeout_seconds

    while time.time() < deadline and found < stop_after:
        resp = await redis.xread({stream: last_id}, count=10, block=1000)
        if not resp:
            continue
        for _stream_name, messages in resp:
            for msg_id, fields in messages:
                last_id = msg_id
                raw = fields.get("payload") or "{}"
                try:
                    data = json.loads(raw)
                except Exception:
                    data = {"raw": raw}

                found += 1
                print(f"\nRECEIPT {found}/{stop_after} id={msg_id}")
                print(json.dumps(data, indent=2))
                if found >= stop_after:
                    return


async def main() -> None:
    parser = argparse.ArgumentParser(description="Publish a demo outbound:http request and tail receipts.")
    parser.add_argument("--redis-url", default="redis://localhost:6379/0")
    parser.add_argument("--requests-stream", default="outbound:requests")
    parser.add_argument("--provider", default="http")
    parser.add_argument("--session-id", default=f"sess_demo_{_now_ms()}")
    parser.add_argument("--event-id", default=f"evt_demo_{uuid.uuid4().hex[:10]}")
    parser.add_argument(
        "--callback-url",
        default="http://127.0.0.1:8010/callbacks/http",
        help="Where the outbound http adapter should POST the provider_payload.",
    )
    parser.add_argument("--timeout", type=float, default=10.0, help="Seconds to wait for receipts")
    parser.add_argument("--stop-after", type=int, default=2, help="Number of receipts to print then exit")

    args = parser.parse_args()

    redis = Redis.from_url(args.redis_url, decode_responses=True)

    # The http adapter will POST provider_payload to callback_url.
    # The outbound service ALSO emits an initial 'queued' receipt after the send call.
    # Then the callback endpoint will emit a second receipt (typically 'delivered').
    payload: Dict[str, Any] = {
        "event_id": args.event_id,
        "session_id": args.session_id,
        "provider": args.provider,
        "callback_url": args.callback_url,
        "trace_id": f"trace_{uuid.uuid4().hex}",
        "provider_payload": {
            # These fields are expected by the generic callback handler to emit a receipt.
            "event_id": args.event_id,
            "session_id": args.session_id,
            "provider_message_id": f"demo_msg_{uuid.uuid4().hex[:8]}",
            "status": "delivered",
        },
    }

    receipt_stream = f"outbound:{args.provider}"

    try:
        msg_id = await _publish_request(redis, stream=args.requests_stream, payload=payload)
        print(f"Published to {args.requests_stream} message_id={msg_id}")
        print(f"Tailing receipts on {receipt_stream} for up to {args.timeout}s...")
        await _read_receipts(redis, stream=receipt_stream, timeout_seconds=args.timeout, stop_after=args.stop_after)
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
