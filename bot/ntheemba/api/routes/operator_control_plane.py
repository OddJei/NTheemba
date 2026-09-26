"""Authenticated operator boundary for Ntheemba business runtime configuration."""

from __future__ import annotations

import hmac
from typing import Any, Literal

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from ntheemba.application.operator_control_plane import (
    OperatorControlPlaneError,
    OperatorControlPlaneService,
)
from ntheemba.config import Settings
from ntheemba.domain.business import (
    BusinessChannel, BusinessIntegration, BusinessProfile, BusinessShop, ChannelRole, ChannelScope,
)

router = APIRouter(prefix="/operator/control-plane", tags=["operator-control-plane"])


class BusinessMutationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    business_id: str = Field(alias="businessId", min_length=1, max_length=160)
    display_name: str = Field(alias="displayName", min_length=1, max_length=200)
    adapter_type: str = Field(alias="adapterType", min_length=1, max_length=120)
    declared_capabilities: list[str] = Field(alias="declaredCapabilities", min_length=1)
    enabled: bool = True
    business_type: str = Field(default="", alias="businessType", max_length=120)
    description: str = Field(default="", max_length=1000)


class ChannelMutationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    channel_instance_id: str = Field(alias="channelInstanceId", min_length=1, max_length=200)
    provider: str = Field(min_length=1, max_length=100)
    business_id: str | None = Field(default=None, alias="businessId", max_length=160)
    phone_e164: str = Field(alias="phoneE164", min_length=8, max_length=30)
    scope: Literal["business", "platform"] = "business"
    role: Literal[
        "business_primary", "business_secondary",
        "marketplace", "platform_general", "platform_support"
    ] = "business_primary"
    is_primary: bool = Field(default=False, alias="isPrimary")
    external_session_id: str = Field(default="", alias="externalSessionId", max_length=200)
    recipient_identifier: str = Field(default="", alias="recipientIdentifier", max_length=200)
    enabled: bool = True


class IntegrationMutationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    integration_id: str = Field(alias="integrationId", min_length=1, max_length=200)
    business_id: str = Field(alias="businessId", min_length=1, max_length=160)
    adapter_type: str = Field(alias="adapterType", min_length=1, max_length=120)
    base_url: str = Field(alias="baseUrl", min_length=1, max_length=1000)
    provider: str = Field(default="tradeflow_http", max_length=100)
    api_version: str = Field(default="tradeflow.ntheemba.v1", alias="apiVersion", max_length=100)
    auth_reference: str = Field(default="", alias="authReference", max_length=300)
    integration_status: Literal["active", "inactive", "testing", "disabled"] = Field(
        default="active", alias="status"
    )
    enabled: bool = True
    capabilities: list[str] = Field(min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)


class ShopMutationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    shop_id: str = Field(alias="shopId", min_length=1, max_length=160)
    display_name: str = Field(alias="displayName", min_length=1, max_length=200)
    status: Literal["active", "inactive"] = "active"
    is_primary: bool = Field(default=False, alias="isPrimary")
    location: dict[str, str] = Field(default_factory=dict)
    hours_status: Literal["unverified", "verified"] = Field(default="unverified", alias="hoursStatus")
    source_revision: str = Field(default="", alias="sourceRevision", max_length=200)


class CapabilityMutationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool
    config: dict[str, object] | None = None


class BusinessEnabledRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


class IntegrationPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    base_url: str | None = Field(default=None, alias="baseUrl", max_length=1000)
    auth_reference: str | None = Field(default=None, alias="authReference", max_length=300)
    enabled: bool | None = None
    integration_status: Literal["active", "inactive", "testing", "disabled"] | None = Field(
        default=None, alias="status"
    )
    capabilities: list[str] | None = None
    config: dict[str, object] | None = None


class ControlPlaneResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str = "ok"
    business_id: str
    runtime_revision: int | None = None
    resource_id: str = ""
    enabled: bool | None = None
    capabilities: list[str] = Field(default_factory=list)
    endpoint_configured: bool | None = None
    auth_reference_configured: bool | None = None


def _authorize(
    settings: Settings,
    authorization: str | None,
    operator_id: str | None,
    request_id: str | None,
) -> tuple[str, str]:
    if not settings.operator_api_enabled or settings.operator_api_token is None:
        raise HTTPException(status_code=503, detail="Operator control plane is not configured.")
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid operator credentials.")
    supplied = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(supplied, settings.operator_api_token.get_secret_value()):
        raise HTTPException(status_code=401, detail="Invalid operator credentials.")
    actor = (operator_id or "").strip()
    correlation = (request_id or "").strip()
    if not actor:
        raise HTTPException(status_code=400, detail="X-Operator-ID is required.")
    allowed_actors = frozenset(
        item.strip() for item in settings.operator_api_allowed_actors.split(",") if item.strip()
    )
    if allowed_actors and actor not in allowed_actors:
        raise HTTPException(status_code=403, detail="Operator is not authorized.")
    if not correlation:
        raise HTTPException(status_code=400, detail="X-Request-ID is required.")
    return actor, correlation


def _service(request: Request) -> OperatorControlPlaneService:
    service = getattr(request.app.state, "operator_control_plane", None)
    if not isinstance(service, OperatorControlPlaneService):
        raise HTTPException(status_code=503, detail="Operator control plane is unavailable.")
    return service


def _error(error: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(error))


@router.post("/businesses", response_model=ControlPlaneResult, status_code=status.HTTP_201_CREATED)
async def register_business(
    payload: BusinessMutationRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    operator_id: str | None = Header(default=None, alias="X-Operator-ID"),
    request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> ControlPlaneResult:
    actor, correlation = _authorize(request.app.state.settings, authorization, operator_id, request_id)
    try:
        business = BusinessProfile(
            payload.business_id,
            payload.display_name,
            payload.adapter_type,
            frozenset(payload.declared_capabilities),
            enabled=payload.enabled,
            business_type=payload.business_type,
            description=payload.description,
            runtime_revision=1,
        )
        result = await _service(request).register_business(
            business, actor_id=actor, request_id=correlation
        )
    except (OperatorControlPlaneError, ValueError) as error:
        raise _error(error) from error
    return ControlPlaneResult(
        business_id=result.business_id,
        runtime_revision=result.runtime_revision,
        resource_id=result.business_id,
        enabled=result.enabled,
        capabilities=sorted(result.declared_capabilities),
    )


@router.post("/channels", response_model=ControlPlaneResult, status_code=status.HTTP_201_CREATED)
async def register_channel(
    payload: ChannelMutationRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    operator_id: str | None = Header(default=None, alias="X-Operator-ID"),
    request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> ControlPlaneResult:
    actor, correlation = _authorize(request.app.state.settings, authorization, operator_id, request_id)
    try:
        result = await _service(request).register_channel(
            BusinessChannel(
                payload.channel_instance_id,
                payload.provider,
                payload.business_id,
                payload.phone_e164,
                enabled=payload.enabled,
                scope=ChannelScope(payload.scope),
                role=ChannelRole(payload.role),
                is_primary=payload.is_primary,
                external_session_id=payload.external_session_id,
                recipient_identifier=payload.recipient_identifier,
            ),
            actor_id=actor,
            request_id=correlation,
        )
    except (OperatorControlPlaneError, ValueError) as error:
        raise _error(error) from error
    return ControlPlaneResult(
        business_id=result.business_id or "__platform__",
        resource_id=result.channel_instance_id,
        enabled=result.enabled,
    )


@router.post("/integrations", response_model=ControlPlaneResult, status_code=status.HTTP_201_CREATED)
async def register_integration(
    payload: IntegrationMutationRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    operator_id: str | None = Header(default=None, alias="X-Operator-ID"),
    request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> ControlPlaneResult:
    actor, correlation = _authorize(request.app.state.settings, authorization, operator_id, request_id)
    try:
        result = await _service(request).register_integration(
            BusinessIntegration(
                payload.integration_id,
                payload.business_id,
                payload.adapter_type,
                payload.base_url,
                provider=payload.provider,
                api_version=payload.api_version,
                auth_reference=payload.auth_reference,
                status=payload.integration_status,
                enabled=payload.enabled,
                capabilities=frozenset(payload.capabilities),
                config=payload.config,
            ),
            actor_id=actor,
            request_id=correlation,
        )
    except (OperatorControlPlaneError, ValueError) as error:
        raise _error(error) from error
    return ControlPlaneResult(
        business_id=result.business_id,
        resource_id=result.integration_id,
        enabled=result.enabled,
        capabilities=sorted(result.capabilities),
        endpoint_configured=True,
        auth_reference_configured=bool(result.auth_reference),
    )


@router.post("/businesses/{business_id}/shops", response_model=ControlPlaneResult, status_code=status.HTTP_201_CREATED)
async def register_shop(
    business_id: str,
    payload: ShopMutationRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    operator_id: str | None = Header(default=None, alias="X-Operator-ID"),
    request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> ControlPlaneResult:
    actor, correlation = _authorize(request.app.state.settings, authorization, operator_id, request_id)
    try:
        shop = await _service(request).register_shop(
            BusinessShop(
                business_id=business_id,
                shop_id=payload.shop_id,
                display_name=payload.display_name,
                status=payload.status,
                is_primary=payload.is_primary,
                location=payload.location,
                hours_status=payload.hours_status,
                source_revision=payload.source_revision,
            ),
            actor_id=actor,
            request_id=correlation,
        )
    except (OperatorControlPlaneError, ValueError) as error:
        raise _error(error) from error
    return ControlPlaneResult(
        business_id=shop.business_id,
        resource_id=shop.shop_id,
        enabled=shop.status == "active",
    )


@router.put(
    "/businesses/{business_id}/capabilities/{capability_id}",
    response_model=ControlPlaneResult,
)
async def set_capability(
    business_id: str,
    capability_id: str,
    payload: CapabilityMutationRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    operator_id: str | None = Header(default=None, alias="X-Operator-ID"),
    request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> ControlPlaneResult:
    actor, correlation = _authorize(request.app.state.settings, authorization, operator_id, request_id)
    try:
        result = await _service(request).set_capability_enabled(
            business_id,
            capability_id,
            enabled=payload.enabled,
            config=payload.config,
            actor_id=actor,
            request_id=correlation,
        )
    except (OperatorControlPlaneError, ValueError) as error:
        raise _error(error) from error
    return ControlPlaneResult(
        business_id=result.business_id,
        runtime_revision=result.runtime_revision,
        resource_id=capability_id,
        enabled=payload.enabled,
        capabilities=sorted(result.declared_capabilities),
    )


@router.patch("/businesses/{business_id}/enabled", response_model=ControlPlaneResult)
async def set_business_enabled(
    business_id: str,
    payload: BusinessEnabledRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    operator_id: str | None = Header(default=None, alias="X-Operator-ID"),
    request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> ControlPlaneResult:
    actor, correlation = _authorize(request.app.state.settings, authorization, operator_id, request_id)
    try:
        result = await _service(request).set_business_enabled(
            business_id,
            enabled=payload.enabled,
            actor_id=actor,
            request_id=correlation,
        )
    except (OperatorControlPlaneError, ValueError) as error:
        raise _error(error) from error
    return ControlPlaneResult(
        business_id=result.business_id,
        runtime_revision=result.runtime_revision,
        resource_id=result.business_id,
        enabled=result.enabled,
        capabilities=sorted(result.declared_capabilities),
    )


@router.patch(
    "/businesses/{business_id}/integrations/{integration_id}",
    response_model=ControlPlaneResult,
)
async def update_integration(
    business_id: str,
    integration_id: str,
    payload: IntegrationPatchRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    operator_id: str | None = Header(default=None, alias="X-Operator-ID"),
    request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> ControlPlaneResult:
    actor, correlation = _authorize(request.app.state.settings, authorization, operator_id, request_id)
    try:
        result = await _service(request).update_integration(
            business_id,
            integration_id,
            base_url=payload.base_url,
            auth_reference=payload.auth_reference,
            enabled=payload.enabled,
            status=payload.integration_status,
            capabilities=(
                None if payload.capabilities is None else frozenset(payload.capabilities)
            ),
            config=payload.config,
            actor_id=actor,
            request_id=correlation,
        )
    except (OperatorControlPlaneError, ValueError) as error:
        raise _error(error) from error
    return ControlPlaneResult(
        business_id=result.business_id,
        resource_id=result.integration_id,
        enabled=result.enabled,
        capabilities=sorted(result.capabilities),
        endpoint_configured=True,
        auth_reference_configured=bool(result.auth_reference),
    )
