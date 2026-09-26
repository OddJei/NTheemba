"""Validate operations and capability support before invoking TradeFlow."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from datetime import timedelta
from typing import Any

from ntheemba.domain.business import ResolvedBusinessContext
from ntheemba.domain.tradeflow_contract import (
    TradeFlowOperation,
    TradeFlowRequest,
    TradeFlowResponse,
    UnknownTradeFlowOperationError,
    capability_for_operation,
    parse_tradeflow_operation,
    validate_required_payload,
)
from ntheemba.ports.businesses import (
    UnsupportedDeclarationKind,
    UnsupportedDeclarationObservation,
    UnsupportedDeclarationSink,
)
from ntheemba.ports.idempotency import IdempotencyStatus, IdempotencyStore
from ntheemba.ports.tradeflow_contract import TradeFlowContractAdapter

OperationHandler = Callable[[TradeFlowRequest], Awaitable[Mapping[str, Any]]]
IntegrationAdapterFactory = Callable[[ResolvedBusinessContext], TradeFlowContractAdapter]


class IntegrationUnavailableError(LookupError):
    """Raised when no enabled integration can satisfy a capability."""


class InMemoryTradeFlowContractAdapter:
    """Deterministic operation handler map for adapter contract tests."""

    def __init__(
        self,
        *,
        business_id: str,
        handlers: Mapping[TradeFlowOperation, OperationHandler],
    ) -> None:
        if not business_id.strip():
            raise ValueError("business_id must not be empty")
        self.business_id = business_id
        self.handlers = dict(handlers)
        self.requests: list[TradeFlowRequest] = []

    def supports_operation(self, operation: object) -> bool:
        return operation in self.handlers

    async def execute(self, request: TradeFlowRequest) -> TradeFlowResponse:
        if request.business_id != self.business_id:
            return TradeFlowResponse(
                request_id=request.request_id,
                business_id=request.business_id,
                ok=False,
                error_code="BUSINESS_MISMATCH",
                error_message="The adapter does not own this business.",
            )
        handler = self.handlers.get(request.operation)
        if handler is None:
            return TradeFlowResponse(
                request_id=request.request_id,
                business_id=request.business_id,
                ok=False,
                error_code="OPERATION_NOT_IMPLEMENTED",
                error_message="The adapter has not implemented this known operation.",
            )
        self.requests.append(request)
        data = await handler(request)
        return TradeFlowResponse(
            request_id=request.request_id,
            business_id=request.business_id,
            ok=True,
            data=data,
        )


class CapabilityControlledTradeFlowAdapter:
    """Enforce Ntheemba capability ownership before an adapter call."""

    def __init__(
        self,
        *,
        context: ResolvedBusinessContext,
        inner: TradeFlowContractAdapter,
        observations: UnsupportedDeclarationSink,
    ) -> None:
        self.context = context
        self.inner = inner
        self.observations = observations

    async def execute(self, request: TradeFlowRequest) -> TradeFlowResponse:
        if request.business_id != self.context.business.business_id:
            return TradeFlowResponse(
                request_id=request.request_id,
                business_id=request.business_id,
                ok=False,
                error_code="BUSINESS_MISMATCH",
                error_message="The request business does not match the resolved channel.",
            )
        required = capability_for_operation(request.operation)
        if required not in self.context.capabilities:
            await self.observations.record(
                UnsupportedDeclarationObservation.now(
                    kind=UnsupportedDeclarationKind.TRADEFLOW_OPERATION,
                    value=request.operation.value,
                    business_id=request.business_id,
                    adapter_type=self.context.business.adapter_type,
                    source="adapter_invocation",
                )
            )
            return TradeFlowResponse(
                request_id=request.request_id,
                business_id=request.business_id,
                ok=False,
                error_code="CAPABILITY_NOT_ENABLED",
                error_message="The business has not enabled the required Ntheemba capability.",
            )
        integration = self.context.integration_for(required)
        if integration is None:
            return TradeFlowResponse(
                request_id=request.request_id,
                business_id=request.business_id,
                ok=False,
                error_code="INTEGRATION_NOT_CONFIGURED",
                error_message="No enabled integration is configured for this capability.",
            )
        try:
            validate_required_payload(request)
        except ValueError as error:
            return TradeFlowResponse(
                request_id=request.request_id,
                business_id=request.business_id,
                ok=False,
                error_code="INVALID_TRADEFLOW_REQUEST",
                error_message=str(error),
            )
        if not self.inner.supports_operation(request.operation):
            await self.observations.record(
                UnsupportedDeclarationObservation.now(
                    kind=UnsupportedDeclarationKind.TRADEFLOW_OPERATION,
                    value=request.operation.value,
                    business_id=request.business_id,
                    adapter_type=integration.adapter_type,
                    source="adapter_capability_guard",
                )
            )
            return TradeFlowResponse(
                request_id=request.request_id,
                business_id=request.business_id,
                ok=False,
                error_code="OPERATION_NOT_IMPLEMENTED",
                error_message="The selected integration does not implement this operation.",
            )
        return await self.inner.execute(request)

    def supports_operation(self, operation: object) -> bool:
        return self.inner.supports_operation(operation)


class DynamicTradeFlowIntegrationResolver:
    """Resolve TradeFlow adapters from configured integrations, not business type."""

    def __init__(
        self,
        *,
        factories: Mapping[str, IntegrationAdapterFactory],
        observations: UnsupportedDeclarationSink,
    ) -> None:
        self.factories = dict(factories)
        self.observations = observations

    def resolve(self, context: ResolvedBusinessContext) -> TradeFlowContractAdapter:
        """Return a capability-controlled adapter for the selected integration."""

        integration = context.integration
        if integration is None or not integration.enabled:
            raise IntegrationUnavailableError(
                "No enabled integration is configured for this capability."
            )
        factory = self.factories.get(integration.adapter_type)
        if factory is None:
            raise IntegrationUnavailableError(
                f"No adapter factory is registered for {integration.adapter_type!r}."
            )
        return CapabilityControlledTradeFlowAdapter(
            context=context,
            inner=factory(context),
            observations=self.observations,
        )


class NtheembaTradeFlowIngress:
    """Parse raw adapter requests through Ntheemba's closed operation catalogue.

    A connected TradeFlow edition cannot create a new method by naming it. Unknown
    methods are rejected, observed for review, and never forwarded to an adapter.
    """

    def __init__(
        self,
        *,
        context: ResolvedBusinessContext,
        adapter: TradeFlowContractAdapter,
        observations: UnsupportedDeclarationSink,
    ) -> None:
        self.context = context
        self.adapter = adapter
        self.observations = observations

    async def execute_raw(
        self,
        *,
        request_id: str,
        business_id: str,
        operation: str,
        payload: Mapping[str, Any] | None = None,
        idempotency_key: str = "",
    ) -> TradeFlowResponse:
        """Validate a raw method name before constructing a typed request."""

        try:
            parsed = parse_tradeflow_operation(operation)
        except UnknownTradeFlowOperationError:
            await self.observations.record(
                UnsupportedDeclarationObservation.now(
                    kind=UnsupportedDeclarationKind.TRADEFLOW_OPERATION,
                    value=operation,
                    business_id=business_id,
                    adapter_type=self.context.business.adapter_type,
                    source="raw_adapter_request",
                )
            )
            return TradeFlowResponse(
                request_id=request_id,
                business_id=business_id,
                ok=False,
                error_code="UNKNOWN_TRADEFLOW_OPERATION",
                error_message=(
                    "Ntheemba does not recognise this TradeFlow operation. "
                    "It has been recorded for explicit capability review."
                ),
            )

        request = TradeFlowRequest(
            request_id=request_id,
            business_id=business_id,
            operation=parsed,
            payload=payload or {},
            idempotency_key=idempotency_key,
        )
        return await self.adapter.execute(request)


class IdempotentTradeFlowContractAdapter:
    """Durably protect Ntheemba-known TradeFlow write operations."""

    _WRITE_OPERATIONS = frozenset(
        {
            TradeFlowOperation.CLIENT_CREATE,
            TradeFlowOperation.CLIENT_UPDATE_MINIMAL_PROFILE,
            TradeFlowOperation.ORDER_CREATE_REQUEST,
            TradeFlowOperation.APPOINTMENT_CREATE_REQUEST,
            TradeFlowOperation.APPOINTMENT_RESCHEDULE_REQUEST,
            TradeFlowOperation.APPOINTMENT_CANCEL_REQUEST,
            TradeFlowOperation.HANDOVER_CREATE_REQUEST,
        }
    )

    def __init__(
        self,
        inner: TradeFlowContractAdapter,
        store: IdempotencyStore,
        *,
        ttl: timedelta,
    ) -> None:
        if ttl <= timedelta(0):
            raise ValueError("ttl must be greater than zero")
        self.inner = inner
        self.store = store
        self.ttl = ttl

    def supports_operation(self, operation: object) -> bool:
        return self.inner.supports_operation(operation)

    async def execute(self, request: TradeFlowRequest) -> TradeFlowResponse:
        if request.operation not in self._WRITE_OPERATIONS:
            return await self.inner.execute(request)
        if not request.idempotency_key.strip():
            return TradeFlowResponse(
                request_id=request.request_id,
                business_id=request.business_id,
                ok=False,
                error_code="IDEMPOTENCY_KEY_REQUIRED",
                error_message="This TradeFlow write requires an idempotency key.",
            )
        from uuid import uuid4

        key = (
            f"tradeflow:{request.business_id}:{request.operation.value}:"
            f"{request.idempotency_key}"
        )
        owner = f"OWNER-{uuid4()}"
        claimed = await self.store.claim(key, owner_token=owner, ttl=self.ttl)
        if not claimed:
            existing = await self.store.get(key)
            if existing is None or existing.status == IdempotencyStatus.PENDING:
                return TradeFlowResponse(
                    request_id=request.request_id,
                    business_id=request.business_id,
                    ok=False,
                    error_code="IDEMPOTENCY_IN_PROGRESS",
                    error_message="The same TradeFlow action is already being processed.",
                )
            return self._response_from_record(request, existing.result)
        try:
            response = await self.inner.execute(request)
        except Exception:
            await self.store.release(key, owner_token=owner)
            raise
        payload = {
            "ok": response.ok,
            "data": dict(response.data),
            "error_code": response.error_code,
            "error_message": response.error_message,
            "schema_version": response.schema_version,
        }
        await self.store.complete(key, owner_token=owner, result=payload, ttl=self.ttl)
        return response

    @staticmethod
    def _response_from_record(
        request: TradeFlowRequest,
        result: Mapping[str, Any],
    ) -> TradeFlowResponse:
        return TradeFlowResponse(
            request_id=request.request_id,
            business_id=request.business_id,
            ok=bool(result.get("ok")),
            data=dict(result.get("data", {})),
            error_code=str(result.get("error_code", "")),
            error_message=str(result.get("error_message", "")),
            schema_version=str(result.get("schema_version", "tradeflow.ntheemba.v1")),
        )
