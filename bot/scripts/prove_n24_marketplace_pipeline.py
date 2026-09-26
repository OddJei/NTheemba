"""Fail-closed local N24 Marketplace-to-order acceptance proof.

This script never creates, reviews, or publishes an NCPC record.  An owner must
first supply one manually reviewed synthetic PRD/VAR pair in the local Compose
environment.  It then provisions only synthetic Ntheemba control-plane rows and
uses the developer queue endpoint plus a separately running worker.
"""

# This executable keeps its SQL and request fixtures readable on single lines.
# ruff: noqa: E501

from __future__ import annotations

import asyncio
import json
import os
from uuid import uuid4

import httpx
from ntheemba.adapters.ncpc import HttpNCPCAdapter

BASE_URL = os.getenv("NTHEEMBA_PIPELINE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
PLATFORM_CHANNEL_ID = "n24-marketplace-platform"
PLATFORM_RECIPIENT = "+260970099025"
BUSINESS_A = os.getenv("N24_MARKETPLACE_BUSINESS_A_ID", "n24-marketplace-a")
BUSINESS_B = os.getenv("N24_MARKETPLACE_BUSINESS_B_ID", "n24-marketplace-b")
ORDER_A = os.getenv("N24_MARKETPLACE_BUSINESS_A_ORDER_ID", "ORD-N24-MARKET-A")
ORDER_B = os.getenv("N24_MARKETPLACE_BUSINESS_B_ORDER_ID", "ORD-N24-MARKET-B")


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required; use a manually NCPC-reviewed synthetic identity")
    return value


async def _verify_owner_identity() -> tuple[str, str, str]:
    """Read and validate the owner's published identity without mutating NCPC."""

    product_id = _required("N24_MARKETPLACE_NCPC_PRODUCT_ID")
    variant_id = _required("N24_MARKETPLACE_NCPC_VARIANT_ID")
    query = _required("N24_MARKETPLACE_QUERY")
    base_url = _required("NTHEEMBA_NCPC_BASE_URL")
    token = _required("NTHEEMBA_NCPC_API_TOKEN")
    adapter = HttpNCPCAdapter(
        base_url=base_url,
        bearer_token=token,
        allow_local_http_hosts=frozenset({"ncpc"}),
    )
    canonical = await adapter.get_product(variant_id)
    if (
        canonical is None
        or canonical.product_id != product_id
        or canonical.variant_id != variant_id
    ):
        raise RuntimeError("the supplied identity is not a matching published NCPC product/variant")
    return product_id, variant_id, query


async def _provision_ntheemba_only() -> None:
    """Create idempotent synthetic Ntheemba routing/listing state only."""

    import psycopg
    from psycopg.types.json import Jsonb

    dsn = _required("NTHEEMBA_POSTGRES_DSN")
    rows = (
        (
            BUSINESS_A,
            "N24 Marketplace Business A",
            "n24-marketplace-a-tradeflow",
            "https://tradeflow-acceptance:8443/exec",
        ),
        (
            BUSINESS_B,
            "N24 Marketplace Business B",
            "n24-marketplace-b-tradeflow",
            "https://tradeflow-acceptance-b:8443/exec",
        ),
    )
    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as connection:
        for business_id, name, integration_id, base_url in rows:
            await connection.execute(
                """
                INSERT INTO businesses (business_id, display_name, adapter_type, business_type, description, enabled, runtime_revision)
                VALUES (%s, %s, 'tradeflow_standard', 'acceptance', 'Synthetic local N24 Marketplace proof', TRUE, 1)
                ON CONFLICT (business_id) DO UPDATE SET display_name = EXCLUDED.display_name,
                    enabled = TRUE, runtime_revision = businesses.runtime_revision + 1, updated_at = now()
                """,
                (business_id, name),
            )
            await connection.execute(
                """
                INSERT INTO business_capabilities (business_id, capability_id, enabled)
                VALUES (%s, 'product.catalogue', TRUE), (%s, 'product.order', TRUE), (%s, 'fulfilment.collection', TRUE)
                ON CONFLICT (business_id, capability_id) DO UPDATE SET enabled = TRUE
                """,
                (business_id, business_id, business_id),
            )
            await connection.execute(
                """
                INSERT INTO business_integrations (integration_id, business_id, provider, adapter_type, base_url, api_version, auth_reference, status, enabled, capabilities, config)
                VALUES (%s, %s, 'tradeflow_http', 'tradeflow_standard', %s, 'tradeflow.ntheemba.v1', 'env:TRADEFLOW_ACCEPTANCE_TOKEN', 'active', TRUE, ARRAY['product.catalogue', 'product.order'], %s)
                ON CONFLICT (integration_id) DO UPDATE SET business_id = EXCLUDED.business_id,
                    base_url = EXCLUDED.base_url, status = 'active', enabled = TRUE,
                    capabilities = EXCLUDED.capabilities, config = EXCLUDED.config, updated_at = now()
                """,
                (
                    integration_id,
                    business_id,
                    base_url,
                    Jsonb({"contract": "tradeflow.ntheemba.v1", "timeout_seconds": 3.0}),
                ),
            )
            await connection.execute(
                """
                INSERT INTO marketplace_business_listings (business_id, status, discoverable, metadata)
                VALUES (%s, 'active', TRUE, %s)
                ON CONFLICT (business_id) DO UPDATE SET status = 'active', discoverable = TRUE,
                    metadata = EXCLUDED.metadata, updated_at = now()
                """,
                (business_id, Jsonb({"fixture": "n24-local-marketplace"})),
            )
        await connection.execute(
            """
            INSERT INTO business_channels (channel_instance_id, provider, business_id, phone_e164, enabled, scope, role, is_primary, external_session_id, recipient_identifier)
            VALUES (%s, 'openwa-simulator', NULL, %s, TRUE, 'platform', 'marketplace', TRUE, %s, %s)
            ON CONFLICT (channel_instance_id) DO UPDATE SET provider = EXCLUDED.provider, business_id = NULL,
                phone_e164 = EXCLUDED.phone_e164, enabled = TRUE, scope = 'platform', role = 'marketplace',
                is_primary = TRUE, external_session_id = EXCLUDED.external_session_id,
                recipient_identifier = EXCLUDED.recipient_identifier
            """,
            (PLATFORM_CHANNEL_ID, PLATFORM_RECIPIENT, PLATFORM_CHANNEL_ID, PLATFORM_RECIPIENT),
        )


async def _wait(
    client: httpx.AsyncClient, headers: dict[str, str], request_id: str
) -> dict[str, object]:
    for _ in range(40):
        response = await client.get(
            f"{BASE_URL}/dev/pipeline/requests/{request_id}", headers=headers
        )
        response.raise_for_status()
        payload = response.json()
        events = payload.get("audit_events", [])
        if any(
            item.get("event_type") == "gateway.inbound.acknowledged"
            for item in events
            if isinstance(item, dict)
        ):
            return payload
        await asyncio.sleep(0.25)
    raise RuntimeError(f"worker did not acknowledge {request_id}")


async def run() -> int:
    _product_id, _variant_id, query = await _verify_owner_identity()
    await _provision_ntheemba_only()
    token = _required("NTHEEMBA_DEV_TOOLS_TOKEN")
    headers = {"X-Ntheemba-Dev-Token": token}
    customer = f"+260955{str(int(uuid4()) % 1_000_000).zfill(6)}"
    sequence = (
        ("search", query, "I found these Marketplace options:"),
        ("select", "1", "You selected"),
        ("continue", "continue", "Connecting you to N24 Marketplace Business A"),
        ("quantity", "1", "collection or delivery"),
        ("fulfilment", "collection", "name"),
        ("customer", f"N24 Marketplace Proof {customer}", "Estimated total"),
        ("confirm", "confirm", ORDER_A),
    )
    results: list[dict[str, object]] = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        mode = await client.get(f"{BASE_URL}/dev/pipeline/mode", headers=headers)
        mode.raise_for_status()
        if mode.json().get("mode") != "REAL_QUEUE_PIPELINE":
            raise RuntimeError("developer endpoint is not configured for the real queue pipeline")
        for step, text, expected in sequence:
            request_id = f"DEV-N24-MARKET-{step}-{uuid4().hex}"
            response = await client.post(
                f"{BASE_URL}/dev/pipeline/inbound",
                headers={**headers, "Content-Type": "application/json"},
                json={
                    "request_id": request_id,
                    "message_id": f"MSG-{uuid4().hex}",
                    "channel_instance_id": PLATFORM_CHANNEL_ID,
                    "provider": "openwa-simulator",
                    "recipient_phone": PLATFORM_RECIPIENT,
                    "customer_phone": customer,
                    "text": text,
                },
            )
            response.raise_for_status()
            payload = await _wait(client, headers, request_id)
            outbound = payload.get("outbound", [])
            text_out = "\n".join(
                str(item.get("text") or "") for item in outbound if isinstance(item, dict)
            )
            dead_letters = tuple(payload.get("inbound_dead_letters", ())) + tuple(
                payload.get("outbound_dead_letters", ())
            )
            if expected.casefold() not in text_out.casefold() or dead_letters:
                raise RuntimeError(
                    f"unexpected {step} result: {text_out!r}; dead_letters={len(dead_letters)}"
                )
            results.append(
                {"step": step, "request_id": request_id, "outbound_count": len(outbound)}
            )
    if ORDER_B.casefold() in text_out.casefold():
        raise RuntimeError("BUS-B order marker appeared after selecting BUS-A")
    print(
        json.dumps(
            {
                "status": "PASS",
                "selected_business": BUSINESS_A,
                "rejected_order_marker": ORDER_B,
                "steps": results,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
