from types import MappingProxyType

import pytest

from ntheemba.adapters.businesses import InMemoryBusinessRegistry
from ntheemba.domain.business import BusinessChannel, BusinessIntegration, BusinessProfile
from ntheemba.domain.capabilities import Capability


CAPS = frozenset({Capability.PRODUCT_CATALOGUE.value})


def test_channel_identity_canonicalizes_provider_and_whitespace() -> None:
    channel = BusinessChannel(
        "  channel-a  ",
        "  WAHA  ",
        "BUS-A",
        " +260970000001 ",
        external_session_id=" session-a ",
        recipient_identifier=" +260970000001 ",
    )

    assert channel.channel_instance_id == "channel-a"
    assert channel.provider == "waha"
    assert channel.exact_identity == ("waha", "session-a", "+260970000001")


def test_registry_rejects_provider_case_bypass_for_same_external_channel() -> None:
    business = BusinessProfile("BUS-A", "A", "tradeflow_standard", CAPS)
    first = BusinessChannel(
        "channel-a", "WAHA", "BUS-A", "+260970000001", external_session_id="session-a"
    )
    second = BusinessChannel(
        "channel-b", "waha", "BUS-A", "+260970000001", external_session_id="session-a"
    )

    with pytest.raises(ValueError, match="duplicate external channel identity"):
        InMemoryBusinessRegistry(businesses=(business,), channels=(first, second))


@pytest.mark.parametrize(
    "url",
    [
        "https://localhost/exec",
        "https://127.0.0.1/exec",
        "https://10.0.0.8/exec",
        "https://169.254.169.254/latest/meta-data",
        "https://[::1]/exec",
    ],
)
def test_integration_rejects_literal_non_public_destination(url: str) -> None:
    with pytest.raises(ValueError, match="localhost|non-public IP"):
        BusinessIntegration(
            "tf-a",
            "BUS-A",
            "tradeflow_standard",
            url,
            provider="tradeflow_http",
            auth_reference="env:BUS_A_TOKEN",
            capabilities=CAPS,
        )


def test_integration_rejects_raw_secret_in_auth_reference() -> None:
    with pytest.raises(ValueError, match="opaque secret reference"):
        BusinessIntegration(
            "tf-a",
            "BUS-A",
            "tradeflow_standard",
            "https://tradeflow.example/exec",
            provider="tradeflow_http",
            auth_reference="this-is-a-raw-token",
            capabilities=CAPS,
        )


def test_integration_rejects_secret_bearing_config_but_allows_reference() -> None:
    with pytest.raises(ValueError, match="secret references"):
        BusinessIntegration(
            "tf-a",
            "BUS-A",
            "tradeflow_standard",
            "https://tradeflow.example/exec",
            provider="tradeflow_http",
            auth_reference="env:BUS_A_TOKEN",
            capabilities=CAPS,
            config=MappingProxyType({"signing_secret": "raw-value"}),
        )

    integration = BusinessIntegration(
        "tf-a",
        "BUS-A",
        "tradeflow_standard",
        "https://tradeflow.example/exec",
        provider="tradeflow_http",
        auth_reference="env:BUS_A_TOKEN",
        capabilities=CAPS,
        config=MappingProxyType({"signing_secret_reference": "env:BUS_A_SIGNING_SECRET"}),
    )
    assert integration.config["signing_secret_reference"] == "env:BUS_A_SIGNING_SECRET"
