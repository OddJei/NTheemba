"""Developer-only Phase 12 storage diagnostics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict

from ntheemba.domain.customer_memory import ConsentType
from ntheemba.infrastructure.storage import StorageRuntime

router = APIRouter(prefix="/dev/storage", tags=["developer-storage"], include_in_schema=False)


class ConsentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    customer_id: str
    consent_type: ConsentType
    granted: bool
    source: str = "developer_tool"


def _runtime(request: Request) -> StorageRuntime:
    runtime = getattr(request.app.state, "storage_runtime", None)
    if not isinstance(runtime, StorageRuntime):
        raise HTTPException(status_code=503, detail="Storage runtime is unavailable")
    return runtime


@router.get("")
async def storage_status(request: Request) -> dict[str, object]:
    snapshot = await _runtime(request).snapshot()
    return {
        "opened": snapshot.opened,
        "session_backend": snapshot.session_backend,
        "customer_backend": snapshot.customer_backend,
        "business_backend": snapshot.business_backend,
        "gateway_queue_backend": snapshot.gateway_queue_backend,
        "redis_ready": snapshot.redis_ready,
        "postgres_ready": snapshot.postgres_ready,
        "detail": snapshot.detail,
    }


@router.get("/businesses")
async def businesses(request: Request) -> dict[str, object]:
    runtime = _runtime(request)
    profiles = await runtime.business_registry.list_businesses()
    channels = await runtime.business_registry.list_channels()
    return {
        "businesses": [
            {
                "business_id": item.business_id,
                "display_name": item.display_name,
                "adapter_type": item.adapter_type,
                "enabled": item.enabled,
                "declared_capabilities": sorted(item.declared_capabilities),
            }
            for item in profiles
        ],
        "channels": [
            {
                "channel_instance_id": item.channel_instance_id,
                "provider": item.provider,
                "business_id": item.business_id,
                "phone_e164": item.phone_e164,
                "enabled": item.enabled,
            }
            for item in channels
        ],
    }


@router.get("/unsupported")
async def unsupported(request: Request) -> dict[str, object]:
    observations = await _runtime(request).unsupported_declarations.list_observations()
    return {
        "observations": [
            {
                "kind": item.kind.value,
                "value": item.value,
                "business_id": item.business_id,
                "adapter_type": item.adapter_type,
                "source": item.source,
                "observed_at": item.observed_at.isoformat(),
            }
            for item in observations
        ]
    }


@router.post("/consents")
async def set_consent(payload: ConsentRequest, request: Request) -> dict[str, object]:
    consent = await _runtime(request).customer_memory.set_consent(
        payload.customer_id,
        payload.consent_type,
        payload.granted,
        source=payload.source,
    )
    return {
        "customer_id": consent.customer_id,
        "consent_type": consent.consent_type.value,
        "granted": consent.granted,
        "updated_at": consent.updated_at.isoformat(),
    }


@router.get("/memory/{business_id}/{customer_id}")
async def customer_memory(
    business_id: str,
    customer_id: str,
    request: Request,
    limit: int = Query(default=20, ge=1, le=200),
) -> dict[str, object]:
    runtime = _runtime(request)
    customer = await runtime.customer_directory.get_customer(customer_id)
    link = await runtime.customer_directory.get_business_link(business_id, customer_id)
    summaries = await runtime.customer_memory_repository.list_summaries(
        business_id, customer_id, limit=limit
    )
    questions = await runtime.customer_memory_repository.list_questions(
        business_id, customer_id, limit=limit
    )
    addresses = await runtime.customer_memory_repository.list_addresses(
        customer_id, business_id=business_id
    )
    return {
        "customer": None
        if customer is None
        else {
            "customer_id": customer.customer_id,
            "phone_e164": customer.phone_e164,
            "preferred_name": customer.preferred_name,
            "preferred_language": customer.preferred_language,
            "last_seen_at": customer.last_seen_at.isoformat(),
        },
        "business_client": None
        if link is None
        else {
            "business_id": link.business_id,
            "external_client_id": link.external_client_id,
            "business_display_name": link.business_display_name,
        },
        "addresses": [
            {
                "address_id": item.address_id,
                "label": item.label,
                "location_text": item.location_text,
                "business_id": item.business_id,
                "is_default": item.is_default,
            }
            for item in addresses
        ],
        "summaries": [
            {
                "summary_id": item.summary_id,
                "intent": item.intent,
                "outcome": item.outcome,
                "topic": item.topic,
                "created_at": item.created_at.isoformat(),
                "summary": dict(item.summary),
            }
            for item in summaries
        ],
        "questions": [
            {
                "question_id": item.question_id,
                "topic": item.topic,
                "outcome": item.outcome.value,
                "created_at": item.created_at.isoformat(),
            }
            for item in questions
        ],
    }


@router.post("/cleanup")
async def cleanup(request: Request) -> dict[str, int]:
    runtime = _runtime(request)
    now = datetime.now(UTC)
    settings = runtime.settings
    result = await runtime.customer_memory_repository.cleanup(
        message_cutoff=now - timedelta(days=settings.customer_message_retention_days),
        summary_cutoff=now - timedelta(days=settings.customer_summary_retention_days),
        question_cutoff=now - timedelta(days=settings.customer_question_retention_days),
        unsupported_cutoff=now
        - timedelta(days=settings.unsupported_observation_retention_days),
    )
    return {
        "messages_deleted": result.messages_deleted,
        "summaries_deleted": result.summaries_deleted,
        "questions_deleted": result.questions_deleted,
        "unsupported_observations_deleted": result.unsupported_observations_deleted,
    }
