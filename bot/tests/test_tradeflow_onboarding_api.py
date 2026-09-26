from __future__ import annotations

from fastapi.testclient import TestClient
from ntheemba.config import Settings
from ntheemba.main import create_app


def _app():
    return create_app(
        Settings(
            environment="test",
            dev_tools_enabled=False,
            gateway_shared_secret="local-gateway-secret-for-managed-storage-123456",
            tradeflow_self_service_onboarding_enabled=True,
        )
    )


def _contract() -> dict[str, object]:
    return {
        "contractVersion": "tradeflow.ntheemba.onboarding.v1",
        "businessId": "CLIENT-CODE-0001",
        "displayName": "TradeFlow Demo",
        "declaredCapabilities": ["product.catalogue", "business.hours"],
        "integrationId": "tradeflow-client-code-0001",
        "baseUrl": "https://tradeflow.example/exec",
        "shops": [{
            "shopId": "shop-main", "displayName": "Main Shop", "isPrimary": True,
            "location": {"province_name": "Lusaka", "district_name": "Lusaka"},
            "hoursStatus": "unverified",
        }],
    }


def test_tradeflow_onboarding_registers_disabled_business_without_operator_token() -> None:
    with TestClient(_app()) as client:
        response = client.post(
            "/api/v1/onboarding/tradeflow/register",
            headers={"X-Request-ID": "TF-ONBOARD-1"},
            json=_contract(),
        )
        assert response.status_code == 201, response.text
        assert response.json()["customerWorkflows"] == "disabled"
        assert response.json()["issuedTradeFlowApiToken"]
        registry = client.app.state.storage_runtime.business_registry
        business = __import__("asyncio").run(registry.get_business("CLIENT-CODE-0001"))
        assert business is not None and business.enabled is False
        shops = __import__("asyncio").run(registry.list_shops("CLIENT-CODE-0001"))
        assert shops[0].shop_id == "shop-main"
