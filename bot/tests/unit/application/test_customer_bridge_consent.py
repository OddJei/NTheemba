"""Cross-business name sharing remains explicitly consented."""

import pytest

from ntheemba.adapters.customers import InMemoryCustomerDirectory
from ntheemba.application.customer_bridge import CustomerBridgeService
from ntheemba.application.customer_memory import CustomerMemoryService
from ntheemba.domain.customer_memory import ConsentType
from ntheemba.domain.customers import MinimalBusinessClient
from ntheemba.infrastructure.memory import MemoryCustomerMemoryRepository


class ClientPort:
    async def find_client_by_phone(self, _business_id: str, _phone: str):
        return None

    async def create_minimal_client(self, _business_id, request, *, idempotency_key):
        assert idempotency_key
        return MinimalBusinessClient("CLIENT-1", request.display_name, request.phone_e164)


@pytest.mark.asyncio
async def test_business_client_name_is_not_promoted_without_consent() -> None:
    directory = InMemoryCustomerDirectory()
    memory = CustomerMemoryService(MemoryCustomerMemoryRepository())
    bridge = CustomerBridgeService(
        customers=directory,
        clients=ClientPort(),
        consents=memory,
    )
    customer = await bridge.resolve_platform_customer("0971234567")

    link = await bridge.ensure_business_client(
        business_id="serahs-glow-lounge",
        customer_id=customer.customer_id,
        display_name="Natasha",
        idempotency_key="client-1",
    )

    updated = await directory.get_customer(customer.customer_id)
    assert link.business_display_name == "Natasha"
    assert updated is not None
    assert updated.preferred_name == ""
    assert await bridge.reusable_platform_name(customer.customer_id) == ""


@pytest.mark.asyncio
async def test_cross_business_name_consent_allows_platform_name_reuse() -> None:
    directory = InMemoryCustomerDirectory()
    memory = CustomerMemoryService(MemoryCustomerMemoryRepository())
    bridge = CustomerBridgeService(
        customers=directory,
        clients=ClientPort(),
        consents=memory,
    )
    customer = await bridge.resolve_platform_customer("0971234567")
    await memory.set_consent(
        customer.customer_id,
        ConsentType.CROSS_BUSINESS_NAME,
        True,
        source="customer_chat",
    )

    await bridge.ensure_business_client(
        business_id="serahs-glow-lounge",
        customer_id=customer.customer_id,
        display_name="Natasha",
        idempotency_key="client-1",
    )

    assert await bridge.reusable_platform_name(customer.customer_id) == "Natasha"
