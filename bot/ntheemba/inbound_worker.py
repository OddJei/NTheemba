"""Executable reliable inbound worker for Ntheemba's deterministic runtime."""

from __future__ import annotations

import asyncio

from ntheemba.adapters.llm import (
    GeminiIntentProvider,
    GeminiReplyTextProvider,
    build_gemini_client_from_settings,
)
from ntheemba.adapters.ncpc import HttpNCPCAdapter
from ntheemba.adapters.tradeflow import HttpTradeFlowPortFactory
from ntheemba.application.gateway_worker import WorkerAction
from ntheemba.application.inbound_runtime import build_inbound_processing_runtime
from ntheemba.config import Settings, get_settings
from ntheemba.infrastructure.managed_secrets import (
    ManagedOrEnvironmentSecretResolver,
    load_managed_secrets,
)
from ntheemba.infrastructure.storage import build_storage_runtime
from ntheemba.services.reply_localization import (
    ReplyLocalizationConfig,
    SafeReplyLocalizer,
)


class InboundWorkerConfigurationError(RuntimeError):
    """Raised when a standalone worker cannot share durable state safely."""


def validate_inbound_worker_settings(settings: Settings) -> None:
    """Require durable cross-process backends and the shared NCPC read endpoint."""

    if settings.gateway_queue_backend != "redis":
        raise InboundWorkerConfigurationError(
            "gateway_queue_backend must be redis for the standalone inbound worker"
        )
    if settings.session_backend != "redis":
        raise InboundWorkerConfigurationError(
            "session_backend must be redis for the standalone inbound worker"
        )
    if settings.business_backend != "postgres":
        raise InboundWorkerConfigurationError(
            "business_backend must be postgres for the standalone inbound worker"
        )
    if settings.customer_backend != "postgres":
        raise InboundWorkerConfigurationError(
            "customer_backend must be postgres for the standalone inbound worker"
        )
    if not settings.ncpc_base_url:
        raise InboundWorkerConfigurationError("ncpc_base_url is required for the inbound worker")
    if settings.ncpc_api_token is None:
        raise InboundWorkerConfigurationError("ncpc_api_token is required for the inbound worker")


async def run_inbound_worker(settings: Settings | None = None) -> None:
    """Run the reliable inbound queue processor until the process is cancelled."""

    resolved = settings or get_settings()
    validate_inbound_worker_settings(resolved)
    storage = build_storage_runtime(resolved)
    await storage.open()
    try:
        managed_secrets = await load_managed_secrets(storage, resolved)
        ncpc = HttpNCPCAdapter(
            base_url=resolved.ncpc_base_url,
            bearer_token=resolved.ncpc_api_token.get_secret_value(),
            timeout_seconds=resolved.ncpc_timeout_seconds,
            allow_development_internal_ncpc=(
                resolved.environment in {"development", "test"}
                and resolved.ncpc_base_url == "http://ncpc:8080"
            ),
        )
        gemini = build_gemini_client_from_settings(resolved)
        intent_model = GeminiIntentProvider(gemini) if gemini is not None else None
        reply_localizer = (
            SafeReplyLocalizer(
                provider=GeminiReplyTextProvider(gemini),
                config=ReplyLocalizationConfig(
                    enabled=True,
                    blend=resolved.local_language_blend,
                    languages=resolved.local_language_variant_list,
                ),
            )
            if gemini is not None and resolved.reply_localization_enabled
            else None
        )
        composed = build_inbound_processing_runtime(
            storage=storage,
            ncpc=ncpc,
            tradeflow_factory=HttpTradeFlowPortFactory(
                secrets=ManagedOrEnvironmentSecretResolver(managed_secrets),
            ),
            audit=storage.audit_sink,
            consumer_id=resolved.inbound_worker_consumer_id,
            max_attempts=resolved.gateway_max_delivery_attempts,
            model=intent_model,
            reply_localizer=reply_localizer,
        )
        while True:
            result = await composed.worker.run_once()
            if result.action == WorkerAction.IDLE:
                await asyncio.sleep(resolved.inbound_worker_poll_seconds)
    finally:
        await storage.close()


def main() -> None:
    """CLI entry point."""

    asyncio.run(run_inbound_worker())


if __name__ == "__main__":
    main()
