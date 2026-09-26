"""Prove the local gateway -> Redis -> worker -> NCPC -> TradeFlow pipeline."""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ntheemba.adapters.ncpc import HttpNCPCAdapter
from ntheemba.adapters.secrets import EnvironmentSecretResolver
from ntheemba.adapters.tradeflow import HttpTradeFlowPortFactory
from ntheemba.application.gateway_worker import WorkerAction
from ntheemba.application.inbound_runtime import build_inbound_processing_runtime
from ntheemba.config import Settings, get_settings
from ntheemba.infrastructure.redis.keys import RedisKeyspace
from ntheemba.infrastructure.storage import build_storage_runtime
from ntheemba.ports.gateway import ClaimedOutboundMessage

BUSINESS_ID = "n24-acceptance-shop"
CHANNEL_ID = "n24-acceptance-wa"
INTEGRATION_ID = "n24-acceptance-tradeflow"
RECIPIENT_PHONE = "+260970099024"
TRADEFLOW_URL = "https://tradeflow-acceptance:8443/exec"
TRADEFLOW_TOKEN_REF = "env:TRADEFLOW_ACCEPTANCE_TOKEN"


async def _seed_acceptance_business(settings: Settings) -> None:
    import psycopg
    from psycopg.types.json import Jsonb

    dsn = settings.postgres_connection_dsn
    if dsn is None:
        raise RuntimeError("NTHEEMBA_POSTGRES_DSN is required")
    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as connection:
        await connection.execute(
            """
            INSERT INTO businesses (
                business_id, display_name, adapter_type, business_type,
                description, enabled, runtime_revision
            )
            VALUES (
                %s, 'N24 Acceptance Shop', 'tradeflow_standard', 'acceptance',
                'Synthetic local acceptance business', TRUE, 1
            )
            ON CONFLICT (business_id) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                adapter_type = EXCLUDED.adapter_type,
                business_type = EXCLUDED.business_type,
                description = EXCLUDED.description,
                enabled = EXCLUDED.enabled,
                runtime_revision = businesses.runtime_revision + 1,
                updated_at = now()
            """,
            (BUSINESS_ID,),
        )
        await connection.execute(
            """
            INSERT INTO business_capabilities (business_id, capability_id, enabled)
            VALUES
                (%s, 'product.catalogue', TRUE),
                (%s, 'product.order', TRUE),
                (%s, 'fulfilment.collection', TRUE)
            ON CONFLICT (business_id, capability_id) DO UPDATE SET
                enabled = EXCLUDED.enabled
            """,
            (BUSINESS_ID, BUSINESS_ID, BUSINESS_ID),
        )
        await connection.execute(
            """
            INSERT INTO business_channels (
                channel_instance_id, provider, business_id, phone_e164, enabled,
                scope, role, is_primary, external_session_id, recipient_identifier
            )
            VALUES (
                %s, 'openwa-simulator', %s, %s, TRUE,
                'business', 'business_primary', TRUE, %s, %s
            )
            ON CONFLICT (channel_instance_id) DO UPDATE SET
                provider = EXCLUDED.provider,
                business_id = EXCLUDED.business_id,
                phone_e164 = EXCLUDED.phone_e164,
                enabled = EXCLUDED.enabled,
                scope = EXCLUDED.scope,
                role = EXCLUDED.role,
                is_primary = EXCLUDED.is_primary,
                external_session_id = EXCLUDED.external_session_id,
                recipient_identifier = EXCLUDED.recipient_identifier
            """,
            (CHANNEL_ID, BUSINESS_ID, RECIPIENT_PHONE, CHANNEL_ID, RECIPIENT_PHONE),
        )
        await connection.execute(
            """
            INSERT INTO business_integrations (
                integration_id, business_id, provider, adapter_type, base_url,
                api_version, auth_reference, status, enabled, capabilities, config
            )
            VALUES (
                %s, %s, 'tradeflow_http', 'tradeflow_standard', %s,
                'tradeflow.ntheemba.v1', %s, 'testing', TRUE,
                ARRAY['product.catalogue', 'product.order'], %s
            )
            ON CONFLICT (integration_id) DO UPDATE SET
                business_id = EXCLUDED.business_id,
                provider = EXCLUDED.provider,
                adapter_type = EXCLUDED.adapter_type,
                base_url = EXCLUDED.base_url,
                api_version = EXCLUDED.api_version,
                auth_reference = EXCLUDED.auth_reference,
                status = EXCLUDED.status,
                enabled = EXCLUDED.enabled,
                capabilities = EXCLUDED.capabilities,
                config = EXCLUDED.config,
                updated_at = now()
            """,
            (
                INTEGRATION_ID,
                BUSINESS_ID,
                TRADEFLOW_URL,
                TRADEFLOW_TOKEN_REF,
                Jsonb({"contract": "tradeflow.ntheemba.v1", "timeout_seconds": 3.0}),
            ),
        )


async def _enqueue_through_api(
    settings: Settings,
    request_id: str,
    message_id: str,
    customer_phone: str,
    text: str,
) -> None:
    if settings.gateway_shared_secret is None:
        raise RuntimeError("NTHEEMBA_GATEWAY_SHARED_SECRET is required")
    body = {
        "requestId": request_id,
        "messageId": message_id,
        "channelInstanceId": CHANNEL_ID,
        "provider": "openwa-simulator",
        "recipientPhone": RECIPIENT_PHONE,
        "customerPhone": customer_phone,
        "text": text,
        "receivedAt": datetime.now(UTC).isoformat(),
    }
    headers = {
        "Authorization": f"Bearer {settings.gateway_shared_secret.get_secret_value()}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(
            "http://ntheemba:8000/api/v1/gateway/inbound",
            json=body,
            headers=headers,
        )
    if response.status_code >= 400:
        raise RuntimeError(f"gateway enqueue failed: {response.status_code} {response.text}")


async def _clear_stale_proof_messages(settings: Settings) -> int:
    from redis.asyncio import Redis

    redis_url = settings.redis_dsn
    if redis_url is None:
        raise RuntimeError("NTHEEMBA_REDIS_URL is required")
    keyspace = RedisKeyspace(settings.redis_key_prefix, settings.environment)
    streams = (
        keyspace.gateway_inbound_stream(),
        keyspace.gateway_outbound_stream(),
        keyspace.gateway_inbound_dead_letter_stream(),
        keyspace.gateway_outbound_dead_letter_stream(),
    )
    removed = 0
    client = Redis.from_url(redis_url, decode_responses=True, socket_timeout=5)
    try:
        for stream in streams:
            entries = await client.xrange(stream, min="-", max="+")
            stale_ids = [
                entry_id
                for entry_id, fields in entries
                if '"request_id":"REQ-N24-' in str(fields.get("payload") or "")
            ]
            if stale_ids:
                removed += await client.xdel(stream, *stale_ids)
    finally:
        await client.aclose()
    return removed


async def _process_until_replies(
    storage,
    runtime,
    request_id: str,
    worker_actions: list[str],
) -> tuple[ClaimedOutboundMessage, ...]:
    """Process one inbound delivery and drain every reply for its request ID.

    A product selection in an order flow can legitimately publish both the
    product detail and the quantity prompt.  The proof must acknowledge both
    messages before submitting the next customer turn; otherwise it would
    leave an old prompt in the stream and test an invalid transition.
    """

    sender_id = f"n24-proof-sender-{uuid4().hex}"
    for _attempt in range(10):
        result = await runtime.worker.run_once()
        worker_actions.append(result.action.value)
        if result.action not in {WorkerAction.ACKNOWLEDGED, WorkerAction.IDLE}:
            raise RuntimeError(f"worker did not acknowledge message: {result}")
        replies: list[ClaimedOutboundMessage] = []
        for _claim in range(10):
            claimed = await storage.gateway_queue.claim_outbound(sender_id)
            if claimed is None:
                break
            if claimed.message.request_id == request_id:
                replies.append(claimed)
                await storage.gateway_queue.acknowledge_outbound(
                    claimed.delivery_id,
                    sender_id,
                )
                continue
            if claimed.message.request_id.startswith("REQ-N24-"):
                await storage.gateway_queue.acknowledge_outbound(
                    claimed.delivery_id,
                    sender_id,
                )
                continue
            await storage.gateway_queue.retry_outbound(claimed.delivery_id, sender_id)
            raise RuntimeError(
                f"unexpected non-proof outbound request_id: {claimed.message.request_id}"
            )
        if replies:
            return tuple(replies)
    raise RuntimeError(f"no outbound reply was queued for {request_id}; actions={worker_actions}")


async def _send_and_claim_reply(
    *,
    settings: Settings,
    storage,
    runtime,
    customer_phone: str,
    text: str,
    step: str,
    worker_actions: list[str],
) -> tuple[ClaimedOutboundMessage, ...]:
    request_id = f"REQ-N24-{step}-{uuid4().hex}"
    await _enqueue_through_api(
        settings,
        request_id,
        f"MSG-N24-{step}-{uuid4().hex}",
        customer_phone,
        text,
    )
    return await _process_until_replies(storage, runtime, request_id, worker_actions)


async def run() -> int:
    settings = get_settings()
    await _seed_acceptance_business(settings)
    removed_stale = await _clear_stale_proof_messages(settings)
    customer_phone = f"+260955{str(int(uuid4()) % 1_000_000).zfill(6)}"

    storage = build_storage_runtime(settings)
    await storage.open()
    try:
        local_acceptance = settings.local_acceptance_enabled and settings.environment in {
            "development",
            "test",
        }
        ncpc = HttpNCPCAdapter(
            base_url=settings.ncpc_base_url,
            bearer_token=settings.ncpc_api_token.get_secret_value()
            if settings.ncpc_api_token is not None
            else "",
            timeout_seconds=settings.ncpc_timeout_seconds,
            allow_local_http_hosts=frozenset({"ncpc"}) if local_acceptance else frozenset(),
        )
        runtime = build_inbound_processing_runtime(
            storage=storage,
            ncpc=ncpc,
            tradeflow_factory=HttpTradeFlowPortFactory(
                secrets=EnvironmentSecretResolver(),
                allow_insecure_local_tls_hosts=(
                    frozenset({"tradeflow-acceptance"}) if local_acceptance else frozenset()
                ),
            ),
            audit=storage.audit_sink,
            consumer_id=f"n24-proof-{uuid4().hex}",
            max_attempts=1,
        )
        worker_actions: list[str] = []
        first_replies = await _send_and_claim_reply(
            settings=settings,
            storage=storage,
            runtime=runtime,
            customer_phone=customer_phone,
            text="Order local relish",
            step="start",
            worker_actions=worker_actions,
        )
        first = first_replies[0]
        first_text = "\n".join(reply.message.text for reply in first_replies)
        if "N24 Acceptance Local Relish" not in first_text:
            raise RuntimeError(f"unexpected first outbound text: {first_text}")

        sequence = (
            # The initial order intent leaves an order-owned candidate selection;
            # accepting it publishes product detail and the quantity prompt.
            ("select", "yes", "How many"),
            ("quantity", "1", "collection"),
            ("fulfilment", "collection", "name"),
            ("customer", f"Local Proof Customer {customer_phone}", "Estimated total"),
            ("confirm", "confirm", "ORD-N24-ACCEPTANCE"),
        )
        replies: list[str] = [reply.message.text for reply in first_replies]
        final_request_id = first.message.request_id
        for step, text, expected in sequence:
            outbound_replies = await _send_and_claim_reply(
                settings=settings,
                storage=storage,
                runtime=runtime,
                customer_phone=customer_phone,
                text=text,
                step=step,
                worker_actions=worker_actions,
            )
            outbound_text = "\n".join(reply.message.text for reply in outbound_replies)
            final_request_id = outbound_replies[-1].message.request_id
            replies.extend(reply.message.text for reply in outbound_replies)
            if expected.casefold() not in outbound_text.casefold():
                raise RuntimeError(f"unexpected outbound text for {step}: {outbound_text}")

        print(
            json.dumps(
                {
                    "status": "PASS",
                    "request_id": final_request_id,
                    "removed_stale_proof_messages": removed_stale,
                    "worker_actions": worker_actions,
                    "business_id": first.message.business_id,
                    "channel_instance_id": first.message.channel_instance_id,
                    "customer_phone": customer_phone,
                    "reply_contains": [
                        "N24 Acceptance Local Relish",
                        "Estimated total",
                        "ORD-N24-ACCEPTANCE",
                    ],
                    "reply_count": len(replies),
                    "dependencies": {
                        "gateway_api": "http://ntheemba:8000/api/v1/gateway/inbound",
                        "queue": "redis",
                        "business_registry": "postgres",
                        "sessions": "redis",
                        "customers": "postgres",
                        "ncpc": settings.ncpc_base_url,
                        "tradeflow": TRADEFLOW_URL,
                    },
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    finally:
        await storage.close()


def main() -> None:
    raise SystemExit(asyncio.run(run()))


if __name__ == "__main__":
    main()
