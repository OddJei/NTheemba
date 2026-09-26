"""Run dependency-free Phase 12 contract and durability self-checks."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from ntheemba.application.customer_memory import CustomerMemoryService
from ntheemba.config import Settings
from ntheemba.domain.capabilities import CapabilityCatalogue
from ntheemba.domain.customer_memory import ConsentType
from ntheemba.domain.session import Session
from ntheemba.infrastructure.memory import (
    MemoryCustomerMemoryRepository,
    MemoryIdempotencyStore,
)
from ntheemba.infrastructure.serialization import decode_session, encode_session
from ntheemba.main import create_app
from ntheemba.runtime import run_async


@dataclass(frozen=True, slots=True)
class ValidationResult:
    status: str
    checks: tuple[str, ...]


async def _async_checks(checks: list[str]) -> None:
    store = MemoryIdempotencyStore()
    assert await store.claim("order-1", owner_token="owner-a", ttl=timedelta(days=30))
    assert not await store.claim(
        "order-1",
        owner_token="owner-b",
        ttl=timedelta(days=30),
    )
    checks.append("durable idempotency contract prevents duplicate action claims")

    memory = CustomerMemoryService(MemoryCustomerMemoryRepository())
    assert not await memory.is_allowed("CUST-1", ConsentType.CROSS_BUSINESS_NAME)
    await memory.set_consent(
        "CUST-1",
        ConsentType.CROSS_BUSINESS_NAME,
        True,
        source="phase12-self-check",
    )
    assert await memory.is_allowed("CUST-1", ConsentType.CROSS_BUSINESS_NAME)
    checks.append("cross-business name reuse requires explicit consent")


def main() -> int:
    checks: list[str] = []
    catalogue = CapabilityCatalogue.canonical()
    declaration = catalogue.validate_declarations(
        ["product.catalogue", "tradeflow.enable_itself"]
    )
    assert "tradeflow.enable_itself" in declaration.unknown
    assert catalogue.known_ids()
    checks.append("Ntheemba-owned capability catalogue rejects unknown declarations")

    session = Session.create(
        "serahs-glow-lounge",
        "CUST-1",
        now=datetime(2026, 8, 2, 10, 0, tzinfo=UTC),
        ttl=timedelta(days=7),
    )
    session.conversation_summary = "Booking knotless braids"
    restored = decode_session(encode_session(session))
    assert restored == session
    assert restored.expires_at - restored.started_at == timedelta(days=7)
    checks.append("versioned session serialization preserves seven-day runtime state")

    app = create_app(
        Settings(
            environment="test",
            docs_enabled=False,
            gateway_shared_secret="phase12-validation-secret",
        )
    )
    with TestClient(app) as client:
        ready = client.get("/ready")
        ready.raise_for_status()
        assert ready.json()["checks"]["storage"]["status"] == "ready"
        response = client.post(
            "/api/v1/gateway/inbound",
            headers={"Authorization": "Bearer phase12-validation-secret"},
            json={
                "requestId": "REQ-PHASE12",
                "messageId": "MSG-PHASE12",
                "channelInstanceId": "sim-wa-serahs",
                "provider": "openwa-simulator",
                "recipientPhone": "+260976078440",
                "customerPhone": "+260971234567",
                "text": "I want braids",
                "receivedAt": "2026-08-02T10:00:00+00:00",
            },
        )
        assert response.status_code == 202
        assert response.json()["status"] == "accepted"
    checks.append("authenticated gateway ingestion queues a normalized message")

    migration_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(Path("migrations/postgres").glob("*.sql"))
    )
    assert "FORCE ROW LEVEL SECURITY" in migration_text
    assert "unsupported_declarations" in migration_text
    assert "cleanup_ntheemba_memory" in migration_text
    checks.append("PostgreSQL migrations include tenant isolation and retention")

    run_async(_async_checks(checks))
    result = ValidationResult("passed", tuple(checks))
    print(json.dumps(asdict(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
