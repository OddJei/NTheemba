"""TradeFlow-owned, business-scoped onboarding boundary.

This endpoint is intentionally not an operator-control-plane shortcut.  A
TradeFlow business proves possession of its own enrollment credential and can
only create/update its own disabled customer workflow configuration.
"""

from __future__ import annotations

import hmac
import json
import secrets
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from ntheemba.api.routes.operator_control_plane import _service
from ntheemba.application.operator_control_plane import OperatorControlPlaneError
from ntheemba.config import Settings
from ntheemba.domain.business import BusinessIntegration, BusinessProfile, BusinessShop
from ntheemba.infrastructure.managed_secrets import store_managed_secret

router = APIRouter(prefix="/onboarding/tradeflow", tags=["tradeflow-onboarding"])


class ShopContract(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    shop_id: str = Field(alias="shopId", min_length=1, max_length=160)
    display_name: str = Field(alias="displayName", min_length=1, max_length=200)
    status: Literal["active", "inactive"] = "active"
    is_primary: bool = Field(default=False, alias="isPrimary")
    location: dict[str, str] = Field(default_factory=dict)
    hours_status: Literal["unverified", "verified"] = Field(
        default="unverified", alias="hoursStatus"
    )
    source_revision: str = Field(default="", alias="sourceRevision", max_length=200)


class TradeFlowOnboardingContract(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    contract_version: Literal["tradeflow.ntheemba.onboarding.v1"] = Field(alias="contractVersion")
    business_id: str = Field(alias="businessId", min_length=1, max_length=160)
    display_name: str = Field(alias="displayName", min_length=1, max_length=200)
    business_type: str = Field(default="", alias="businessType", max_length=120)
    declared_capabilities: list[str] = Field(alias="declaredCapabilities", min_length=1)
    integration_id: str = Field(alias="integrationId", min_length=1, max_length=200)
    base_url: str = Field(alias="baseUrl", min_length=1, max_length=1000)
    shops: list[ShopContract] = Field(min_length=1, max_length=3)


def _token_for(settings: Settings, business_id: str) -> str | None:
    secret = settings.tradeflow_onboarding_tokens_json
    if secret is None:
        return None
    try:
        values = json.loads(secret.get_secret_value())
    except json.JSONDecodeError:
        return None
    token = values.get(business_id) if isinstance(values, dict) else None
    return token.strip() if isinstance(token, str) and token.strip() else None


def _authenticate(settings: Settings, authorization: str | None, business_id: str) -> None:
    expected = _token_for(settings, business_id)
    supplied = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if not expected or not hmac.compare_digest(expected, supplied):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid TradeFlow onboarding credential.",
        )


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_tradeflow(
    payload: TradeFlowOnboardingContract,
    request: Request,
    authorization: str | None = Header(default=None),
    request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> dict[str, object]:
    """Register the safe TradeFlow contract with customer workflows disabled."""

    correlation = (request_id or "").strip()
    if not correlation:
        raise HTTPException(status_code=400, detail="X-Request-ID is required.")
    settings = request.app.state.settings
    if settings.tradeflow_self_service_onboarding_enabled:
        if settings.environment not in {"development", "test"}:
            raise HTTPException(status_code=503, detail="Self-service onboarding is unavailable.")
    else:
        _authenticate(settings, authorization, payload.business_id)
    service = _service(request)
    actor = "tradeflow:" + payload.business_id
    managed_reference = "managed:tradeflow-" + secrets.token_hex(16)
    issued_tradeflow_token = secrets.token_urlsafe(32)
    try:
        await store_managed_secret(
            request.app.state.storage_runtime,
            settings,
            managed_reference,
            issued_tradeflow_token,
        )
        business = await service.register_business(
            BusinessProfile(
                business_id=payload.business_id,
                display_name=payload.display_name,
                adapter_type="tradeflow_standard",
                declared_capabilities=frozenset(payload.declared_capabilities),
                enabled=False,
                business_type=payload.business_type,
            ), actor_id=actor, request_id=correlation,
        )
        integration = await service.register_integration(
            BusinessIntegration(
                integration_id=payload.integration_id,
                business_id=payload.business_id,
                adapter_type="tradeflow_standard",
                provider="tradeflow_http",
                base_url=payload.base_url,
                auth_reference=managed_reference,
                status="testing",
                enabled=False,
                capabilities=frozenset(payload.declared_capabilities),
                config={"onboarding_contract_version": payload.contract_version},
            ), actor_id=actor, request_id=correlation + ":integration",
        )
        for index, item in enumerate(payload.shops):
            await service.register_shop(
                BusinessShop(
                    business_id=payload.business_id,
                    shop_id=item.shop_id,
                    display_name=item.display_name,
                    status=item.status,
                    is_primary=item.is_primary,
                    location=item.location,
                    hours_status=item.hours_status,
                    source_revision=item.source_revision,
                ), actor_id=actor, request_id=correlation + ":shop:" + str(index),
            )
    except (OperatorControlPlaneError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {
        "status": "registered_pending_verification",
        "businessId": business.business_id,
        "integrationId": integration.integration_id,
        "shopCount": len(payload.shops),
        "customerWorkflows": "disabled",
        "issuedTradeFlowApiToken": issued_tradeflow_token,
    }
