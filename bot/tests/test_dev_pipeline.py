"""HTTP tests for the developer real-pipeline console."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from ntheemba.api.routes.dev_pipeline import EnqueuePipelineMessageRequest, _audit_events
from ntheemba.config import Settings
from ntheemba.main import create_app


def test_pipeline_console_is_protected_self_contained_ui(client: TestClient) -> None:
    response = client.get("/dev/pipeline")

    assert response.status_code == 200
    assert "Ntheemba Real Pipeline Console" in response.text
    assert "Logic simulator workspace" in response.text
    assert "chat-shaped queue probe" in response.text
    assert "Observed pipeline" in response.text
    assert "Gateway-shaped inbound" in response.text
    assert "Find NCPC identity" in response.text
    assert "/dev/storage/ncpc/products" in response.text
    assert "No price, stock, supplier, policy, barcode" in response.text
    assert "aria-live=\"polite\"" in response.text
    assert "/dev/simulator/workspace" in response.text
    assert "Trace console" in response.text
    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "unsafe-inline" not in response.headers["content-security-policy"]


def test_pipeline_mode_states_real_runtime_requirements(client: TestClient) -> None:
    response = client.get("/dev/pipeline/mode")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "REAL_QUEUE_PIPELINE"
    assert payload["proof_scope"] == "GATEWAY_QUEUE_AND_WORKER_RUNTIME_WHEN_WORKER_IS_RUNNING"
    assert payload["dependencies"]["queue"] == "MEMORY"
    assert payload["dependencies"]["worker"] == "EXTERNAL_REQUIRED"
    assert any("separate inbound worker" in item for item in payload["warnings"])


def test_pipeline_default_recipient_matches_the_visible_n24_channel() -> None:
    payload = EnqueuePipelineMessageRequest(
        channel_instance_id="n24-acceptance-wa",
        customer_phone="+260955381043",
        text="Order local relish",
    )

    assert payload.recipient_phone == "+260970099024"


def test_pipeline_enqueue_and_status_use_gateway_shaped_message(
    client: TestClient,
) -> None:
    response = client.post(
        "/dev/pipeline/inbound",
        json={
            "channel_instance_id": "n24-acceptance-wa",
            "customer_phone": "+260955381043",
            "recipient_phone": "+260955000000",
            "text": "Order local relish",
            "message_id": "DEV-MSG-1",
            "request_id": "DEV-REQ-1",
        },
    )

    assert response.status_code == 200
    accepted = response.json()
    assert accepted["status"] == "accepted"
    assert accepted["request_id"] == "DEV-REQ-1"
    assert accepted["mode"] == "local"

    status = client.get("/dev/pipeline/requests/DEV-REQ-1")
    assert status.status_code == 200
    payload = status.json()
    assert payload["storage"]["gateway_queue_backend"] == "memory"
    assert payload["inbound"][0]["request_id"] == "DEV-REQ-1"
    assert payload["inbound"][0]["message_id"] == "DEV-MSG-1"
    assert payload["inbound"][0]["channel_instance_id"] == "n24-acceptance-wa"
    assert payload["inbound"][0]["customer_phone"] == "+260955381043"
    assert payload["inbound"][0]["text"] == "Order local relish"


def test_pipeline_is_not_registered_outside_developer_environments() -> None:
    app = create_app(
        Settings(
            environment="production",
            dev_tools_enabled=True,
            docs_enabled=False,
            trace_export_enabled=False,
        )
    )
    with TestClient(app) as client:
        assert client.get("/dev/pipeline").status_code == 404
        assert client.get("/dev/pipeline/mode").status_code == 404


def test_pipeline_routes_are_excluded_from_openapi() -> None:
    app = create_app(Settings(environment="test", docs_enabled=True))

    assert all(not path.startswith("/dev/pipeline") for path in app.openapi()["paths"])


@pytest.mark.asyncio
async def test_pipeline_audit_status_supports_postgres_mapping_rows() -> None:
    """The real psycopg pool returns mapping rows, not positional tuples."""

    class Result:
        async def fetchall(self):
            return [
                {
                    "event_id": "AUD-1",
                    "event_type": "message.processed",
                    "business_id": "BUS-1",
                    "severity": "info",
                    "conversation_id": "CONV-1",
                    "message_id": "MSG-1",
                    "occurred_at": datetime(2026, 9, 6, tzinfo=UTC),
                    "data": {"token": "must-not-leak", "safe": "yes"},
                }
            ]

    class Connection:
        async def execute(self, _query, *_args):
            return Result()

    class Pool:
        @asynccontextmanager
        async def connection(self):
            yield Connection()

    runtime = SimpleNamespace(postgres_runtime=SimpleNamespace(pool=Pool()))

    events = await _audit_events(runtime, "REQ-1")

    assert events == [
        {
            "event_id": "AUD-1",
            "event_type": "message.processed",
            "business_id": "BUS-1",
            "severity": "info",
            "conversation_id": "CONV-1",
            "message_id": "MSG-1",
            "occurred_at": "2026-09-06T00:00:00+00:00",
            "data": {"token": "[REDACTED]", "safe": "yes"},
        }
    ]
