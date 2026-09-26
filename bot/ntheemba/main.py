"""FastAPI application factory for Ntheemba."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ntheemba.adapters.tracing import InMemoryTraceSink
from ntheemba.api.routes.dev_auth import router as dev_auth_router
from ntheemba.api.routes.dev_console import router as dev_console_router
from ntheemba.api.routes.dev_dependencies import router as dev_dependencies_router
from ntheemba.api.routes.dev_observability import router as dev_observability_router
from ntheemba.api.routes.dev_pipeline import router as dev_pipeline_router
from ntheemba.api.routes.dev_simulation_lab import router as dev_simulation_lab_router
from ntheemba.api.routes.dev_simulator import router as dev_simulator_router
from ntheemba.api.routes.dev_storage import router as dev_storage_router
from ntheemba.api.routes.dev_tracing import router as dev_tracing_router
from ntheemba.api.routes.gateway import router as gateway_router
from ntheemba.api.routes.health import router as health_router
from ntheemba.api.routes.operator_control_plane import router as operator_control_plane_router
from ntheemba.api.routes.operator_ui import router as operator_ui_router
from ntheemba.api.routes.tradeflow_onboarding import router as tradeflow_onboarding_router
from ntheemba.api.routes.transport import router as transport_router
from ntheemba.api.schemas import ErrorBody, ErrorResponse
from ntheemba.application.operator_control_plane import OperatorControlPlaneService
from ntheemba.application.runtime_profiles import (
    RuntimeProfileCompiler,
    RuntimeProfileConfigurationService,
)
from ntheemba.application.trace_query_service import TraceQueryService
from ntheemba.config import Settings, get_settings
from ntheemba.devtools.fake_dependencies import FakeDependencyController
from ntheemba.devtools.security import (
    DeveloperToolsSecurityMiddleware,
    DeveloperToolsSecurityPolicy,
    DeveloperToolsSessionStore,
)
from ntheemba.devtools.simulator import DeveloperConversationSimulator
from ntheemba.domain.capabilities import CapabilityCatalogue
from ntheemba.infrastructure.errors import NtheembaError
from ntheemba.infrastructure.storage import build_storage_runtime
from ntheemba.observability.bootstrap import build_runtime_trace_sink
from ntheemba.observability.tracer import Tracer
from ntheemba.runtime import configure_asyncio_runtime

configure_asyncio_runtime()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure a Ntheemba FastAPI application."""

    resolved_settings = settings or get_settings()
    storage_runtime = build_storage_runtime(resolved_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await storage_runtime.open()
        app.state.storage_runtime = storage_runtime
        onboarding_enabled = bool(
            resolved_settings.tradeflow_onboarding_tokens_json
            or resolved_settings.tradeflow_self_service_onboarding_enabled
        )
        if resolved_settings.operator_api_enabled or onboarding_enabled:
            compiler = RuntimeProfileCompiler(
                registry=storage_runtime.business_registry,
                catalogue=CapabilityCatalogue.canonical(),
                cache=storage_runtime.runtime_profile_cache,
            )
            app.state.operator_control_plane = OperatorControlPlaneService(
                registry=storage_runtime.business_registry,
                configuration=RuntimeProfileConfigurationService(
                    registry=storage_runtime.business_registry,
                    compiler=compiler,
                ),
                audit=storage_runtime.audit_sink,
            )
        try:
            yield
        finally:
            await storage_runtime.close()

    docs_url = "/docs" if resolved_settings.docs_enabled else None
    openapi_url = "/openapi.json" if resolved_settings.docs_enabled else None
    app = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.version,
        docs_url=docs_url,
        redoc_url=None,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.storage_runtime = storage_runtime

    memory_sink = InMemoryTraceSink() if resolved_settings.developer_tools_active else None
    runtime_trace_sink, observability_runtime = build_runtime_trace_sink(
        resolved_settings,
        memory_sink=memory_sink,
    )
    app.state.runtime_trace_sink = runtime_trace_sink
    app.state.observability_runtime = observability_runtime
    app.state.tracer = Tracer(runtime_trace_sink)

    app.include_router(health_router)
    app.include_router(gateway_router, prefix=resolved_settings.api_prefix)
    app.include_router(transport_router, prefix="/api/v2")
    if (
        resolved_settings.tradeflow_onboarding_tokens_json
        or resolved_settings.tradeflow_self_service_onboarding_enabled
    ):
        app.include_router(tradeflow_onboarding_router, prefix=resolved_settings.api_prefix)
    if resolved_settings.operator_api_enabled:
        app.include_router(operator_control_plane_router, prefix=resolved_settings.api_prefix)
        app.state.operator_ui_sessions = {}
        app.state.operator_ui_actions = {}
        app.include_router(operator_ui_router)
    if resolved_settings.developer_tools_active:
        assert memory_sink is not None
        app.state.trace_sink = memory_sink
        app.state.trace_query_service = TraceQueryService(memory_sink)
        app.state.fake_dependency_controller = FakeDependencyController()
        app.state.conversation_simulator = DeveloperConversationSimulator(
            controller=app.state.fake_dependency_controller,
            tracer=app.state.tracer,
            trace_events=memory_sink.snapshot,
        )
        dev_security_policy = DeveloperToolsSecurityPolicy.from_settings(resolved_settings)
        dev_sessions = DeveloperToolsSessionStore(
            ttl_seconds=resolved_settings.dev_tools_session_ttl_seconds
        )
        app.state.dev_tools_security_policy = dev_security_policy
        app.state.dev_tools_sessions = dev_sessions
        app.add_middleware(
            DeveloperToolsSecurityMiddleware,
            policy=dev_security_policy,
            sessions=dev_sessions,
        )
        app.include_router(dev_auth_router)
        app.include_router(dev_tracing_router)
        app.include_router(dev_dependencies_router)
        app.include_router(dev_observability_router)
        app.include_router(dev_pipeline_router)
        app.include_router(dev_simulator_router)
        app.include_router(dev_simulation_lab_router)
        app.include_router(dev_storage_router)
        app.include_router(dev_console_router)

    @app.exception_handler(NtheembaError)
    async def handle_ntheemba_error(
        _request: object,
        error: NtheembaError,
    ) -> JSONResponse:
        payload = ErrorResponse(
            error=ErrorBody(
                code=error.code,
                message=error.safe_message,
                retryable=error.retryable,
                details=error.details,
            )
        )
        return JSONResponse(status_code=error.status_code, content=payload.model_dump())

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        _request: object,
        error: RequestValidationError,
    ) -> JSONResponse:
        payload = ErrorResponse(
            error=ErrorBody(
                code="REQUEST_VALIDATION_ERROR",
                message="The request could not be validated.",
                retryable=False,
                details={"errors": error.errors()},
            )
        )
        return JSONResponse(status_code=422, content=payload.model_dump())

    return app


app = create_app()
