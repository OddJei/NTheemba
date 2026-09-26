"""Local acceptance stub tests, including the strict two-business fixture mode."""

from fastapi.testclient import TestClient
from ntheemba.devtools.tradeflow_acceptance_stub import app


def _envelope(*, business_id: str, action: str, data: dict[str, object]) -> dict[str, object]:
    return {
        "api_token": "local-test-token",
        "business_id": business_id,
        "action": action,
        "data": data,
    }


def test_stub_returns_linked_identity_only_for_configured_variant(monkeypatch) -> None:
    monkeypatch.setenv("TRADEFLOW_ACCEPTANCE_TOKEN", "local-test-token")
    monkeypatch.setenv("TRADEFLOW_ACCEPTANCE_BUSINESS_ID", "BUS-A")
    monkeypatch.setenv("TRADEFLOW_ACCEPTANCE_PRODUCT_ID", "A-PRODUCT")
    monkeypatch.setenv("TRADEFLOW_ACCEPTANCE_NCPC_PRODUCT_ID", "PRD-LOCAL")
    monkeypatch.setenv("TRADEFLOW_ACCEPTANCE_NCPC_VARIANT_ID", "VAR-LOCAL")
    client = TestClient(app)

    found = client.post(
        "/exec",
        json=_envelope(
            business_id="BUS-A",
            action="catalogue.by_ncpc_variant",
            data={"ncpc_variant_id": "VAR-LOCAL"},
        ),
    )
    assert found.status_code == 200
    item = found.json()["data"]["items"][0]
    assert item["identity"] == {
        "status": "linked",
        "ncpc_prd_id": "PRD-LOCAL",
        "ncpc_var_id": "VAR-LOCAL",
    }

    not_found = client.post(
        "/exec",
        json=_envelope(
            business_id="BUS-A",
            action="catalogue.by_ncpc_variant",
            data={"ncpc_variant_id": "VAR-OTHER"},
        ),
    )
    assert not_found.json()["data"]["items"] == []


def test_stub_rejects_another_business_even_with_a_valid_token(monkeypatch) -> None:
    monkeypatch.setenv("TRADEFLOW_ACCEPTANCE_TOKEN", "local-test-token")
    monkeypatch.setenv("TRADEFLOW_ACCEPTANCE_BUSINESS_ID", "BUS-A")
    client = TestClient(app)

    response = client.post(
        "/exec",
        json=_envelope(
            business_id="BUS-B",
            action="catalogue.search",
            data={"query": "local relish"},
        ),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "TENANT_MISMATCH"
