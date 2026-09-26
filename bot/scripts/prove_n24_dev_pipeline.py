"""Prove the developer real-pipeline endpoint with a separate inbound worker.

Run this only against the local acceptance stack after
``prove_n24_local_pipeline.py`` has provisioned the synthetic N24 business.
It calls the dev-only enqueue/status API; the browser-facing tool never needs
the gateway shared secret.
"""

from __future__ import annotations

import asyncio
import json
import os
from uuid import uuid4

import httpx

BASE_URL = os.getenv("NTHEEMBA_PIPELINE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
CHANNEL_ID = "n24-acceptance-wa"
RECIPIENT_PHONE = "+260970099024"


async def _wait_for_processed(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    request_id: str,
) -> dict[str, object]:
    for _attempt in range(30):
        response = await client.get(
            f"{BASE_URL}/dev/pipeline/requests/{request_id}",
            headers=headers,
        )
        response.raise_for_status()
        payload = response.json()
        audit_events = payload.get("audit_events", [])
        event_types = {
            str(event.get("event_type") or "") for event in audit_events if isinstance(event, dict)
        }
        if "gateway.inbound.acknowledged" in event_types:
            return payload
        await asyncio.sleep(0.25)
    raise RuntimeError(f"pipeline worker did not acknowledge {request_id}")


async def run() -> int:
    token = os.getenv("NTHEEMBA_DEV_TOOLS_TOKEN", "").strip()
    if not token:
        raise RuntimeError("NTHEEMBA_DEV_TOOLS_TOKEN is required")
    headers = {"X-Ntheemba-Dev-Token": token}
    customer_phone = f"+260955{str(int(uuid4()) % 1_000_000).zfill(6)}"
    sequence = (
        ("start", "Order local relish", "N24 Acceptance Local Relish"),
        ("select", "yes", "How many"),
        ("quantity", "1", "collection"),
        ("fulfilment", "collection", "name"),
        ("customer", f"Local Pipeline Customer {customer_phone}", "Estimated total"),
        ("confirm", "confirm", "ORD-N24-ACCEPTANCE"),
    )
    results: list[dict[str, object]] = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        mode = await client.get(f"{BASE_URL}/dev/pipeline/mode", headers=headers)
        mode.raise_for_status()
        if mode.json().get("mode") != "REAL_QUEUE_PIPELINE":
            raise RuntimeError("developer endpoint is not using REAL_QUEUE_PIPELINE mode")

        for step, text, expected in sequence:
            request_id = f"DEV-N24-{step}-{uuid4().hex}"
            response = await client.post(
                f"{BASE_URL}/dev/pipeline/inbound",
                headers={**headers, "Content-Type": "application/json"},
                json={
                    "request_id": request_id,
                    "message_id": f"DEV-N24-MSG-{step}-{uuid4().hex}",
                    "channel_instance_id": CHANNEL_ID,
                    "provider": "openwa-simulator",
                    "recipient_phone": RECIPIENT_PHONE,
                    "customer_phone": customer_phone,
                    "text": text,
                },
            )
            response.raise_for_status()
            payload = await _wait_for_processed(client, headers, request_id)
            outbound = payload.get("outbound", [])
            texts = [str(item.get("text") or "") for item in outbound if isinstance(item, dict)]
            combined = "\n".join(texts)
            dead_letters = tuple(payload.get("inbound_dead_letters", ())) + tuple(
                payload.get("outbound_dead_letters", ())
            )
            if expected.casefold() not in combined.casefold() or dead_letters:
                raise RuntimeError(
                    f"unexpected pipeline result for {step}: "
                    f"outbound={texts!r}, dead_letters={len(dead_letters)}"
                )
            results.append(
                {
                    "step": step,
                    "request_id": request_id,
                    "outbound_count": len(texts),
                    "audit_count": len(payload.get("audit_events", [])),
                }
            )

    print(
        json.dumps(
            {
                "status": "PASS",
                "mode": "REAL_QUEUE_PIPELINE",
                "customer_phone": customer_phone,
                "steps": results,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(run()))


if __name__ == "__main__":
    main()
