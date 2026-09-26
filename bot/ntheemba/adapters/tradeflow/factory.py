"""Build exact tenant TradeFlow adapters from durable integration configuration."""

from __future__ import annotations

from typing import Protocol

import httpx

from ntheemba.adapters.secrets import SecretResolver
from ntheemba.adapters.tradeflow.http import HttpTradeFlowAdapter
from ntheemba.domain.business import BusinessIntegration
from ntheemba.ports.tradeflow import TradeFlowPort


class TradeFlowPortFactory(Protocol):
    """Create a runtime port for one already-resolved business integration."""

    def build(self, integration: BusinessIntegration) -> TradeFlowPort: ...


class HttpTradeFlowPortFactory:
    """Resolve secret references and build a tenant-bound HTTP TradeFlow adapter."""

    def __init__(
        self,
        *,
        secrets: SecretResolver,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._secrets = secrets
        self._client = client

    def build(self, integration: BusinessIntegration) -> TradeFlowPort:
        if integration.provider not in {"google_apps_script", "tradeflow_http"}:
            raise ValueError("unsupported TradeFlow integration provider")
        token = self._secrets.resolve(integration.auth_reference)
        signing_reference = str(integration.config.get("signing_secret_reference") or "").strip()
        signing_secret = self._secrets.resolve(signing_reference) if signing_reference else None
        timeout = float(integration.config.get("timeout_seconds") or 7.0)
        shop_id = str(
            integration.config.get("shop_id")
            or integration.config.get("default_shop_id")
            or ""
        )
        return HttpTradeFlowAdapter(
            business_id=integration.business_id,
            base_url=integration.base_url,
            api_token=token,
            default_shop_id=shop_id,
            signing_secret=signing_secret,
            timeout_seconds=timeout,
            client=self._client,
        )
