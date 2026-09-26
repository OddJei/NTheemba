"""End-to-end tests for Phases 11.12-11.20 developer workspace."""

from fastapi.testclient import TestClient


def _send(
    client: TestClient,
    conversation_id: str,
    text: str,
    index: int,
) -> dict[str, object]:
    response = client.post(
        "/dev/simulator/workspace/messages",
        json={
            "conversation_id": conversation_id,
            "text": text,
            "message_id": f"workspace-message-{conversation_id}-{index}",
            "request_id": f"workspace-request-{conversation_id}-{index}",
        },
    )
    assert response.status_code == 200
    return response.json()


def test_workspace_lists_grouped_businesses_and_seeded_conversations(
    client: TestClient,
) -> None:
    page = client.get("/dev/simulator/workspace")
    assert page.status_code == 200
    assert "Ntheemba Multi-Conversation Simulator" in page.text
    assert "multiple isolated sessions" in page.text

    businesses = client.get("/dev/simulator/workspace/businesses").json()
    assert [item["business_id"] for item in businesses] == [
        "harvest-big-shop",
        "amac-enterprise",
        "serahs-glow-lounge",
    ]
    assert businesses[0]["group"] == "standard"
    assert businesses[2]["group"] == "custom"
    assert "loyalty.read" in businesses[2]["capabilities"]

    catalogue = client.get("/dev/simulator/workspace/capabilities").json()
    ids = {item["capability"] for item in catalogue}
    assert {"product.order", "appointment.create", "loyalty.read"} <= ids
    loyalty = next(item for item in catalogue if item["capability"] == "loyalty.read")
    assert "loyalty.get_status" in loyalty["tradeflow_operations"]

    conversations = client.get("/dev/simulator/workspace/conversations").json()
    assert len(conversations) >= 9
    assert {item["conversation_id"] for item in conversations} >= {
        "conv-harvest-ruth",
        "conv-serah-ruth",
        "conv-serah-natasha",
    }


def test_serah_loyalty_uses_channel_routing_customer_bridge_and_capability_guard(
    client: TestClient,
) -> None:
    payload = _send(
        client,
        "conv-serah-natasha",
        "How many loyalty points do I have?",
        1,
    )

    assert payload["status"] == "processed"
    replies = payload["replies"]
    assert isinstance(replies, list)
    assert "Silver" in replies[0]["text"]
    trace = client.get(
        "/dev/simulator/requests/workspace-request-conv-serah-natasha-1/trace"
    ).json()
    nodes = {event["node_id"] for event in trace}
    assert {
        "gateway.message",
        "business.resolve",
        "capabilities.load",
        "customer.resolve",
        "capabilities.validate",
        "message.interpret",
        "workflow.execute",
    } <= nodes


def test_disabled_telephone_business_capability_is_denied_without_execution(
    client: TestClient,
) -> None:
    payload = _send(
        client,
        "conv-amac-delivery-denied",
        "Order cooking oil for delivery",
        1,
    )

    assert payload["status"] == "processed"
    assert "not enabled" in payload["replies"][0]["text"]
    assert payload["session"]["flow"] == "idle"


def test_same_platform_customer_has_separate_business_sessions(client: TestClient) -> None:
    harvest = _send(client, "conv-harvest-ruth", "What time do you close?", 1)
    serah = _send(
        client,
        "conv-serah-ruth",
        "How many loyalty points do I have?",
        1,
    )

    harvest_session = harvest["session"]
    serah_session = serah["session"]
    assert harvest_session["customer_id"] == serah_session["customer_id"]
    assert harvest_session["business_id"] == "harvest-big-shop"
    assert serah_session["business_id"] == "serahs-glow-lounge"
    assert harvest_session["conversation_id"] != serah_session["conversation_id"]
    assert "Bronze" in serah["replies"][0]["text"]


def test_new_serah_booking_creates_minimal_client_link(client: TestClient) -> None:
    conversations = client.get("/dev/simulator/workspace/conversations").json()
    chanda = next(
        item for item in conversations if item["conversation_id"] == "conv-serah-chanda"
    )
    payload: dict[str, object] = {}
    for index, text in enumerate(chanda["suggested_messages"], start=1):
        payload = _send(client, "conv-serah-chanda", text, index)
        assert payload["status"] == "processed"

    assert payload["session"]["stage"] == "submitted"
    follow_up = _send(
        client,
        "conv-serah-chanda",
        "How many loyalty points do I have?",
        20,
    )
    assert "client profile is recognised" in follow_up["replies"][0]["text"]


def test_workspace_completes_standard_delivery_order_after_product_selection(
    client: TestClient,
) -> None:
    conversation = next(
        item
        for item in client.get("/dev/simulator/workspace/conversations").json()
        if item["conversation_id"] == "conv-harvest-ruth"
    )

    result: dict[str, object] = {}
    for index, text in enumerate(conversation["suggested_messages"], start=1):
        result = _send(client, conversation["conversation_id"], text, index)

    assert result["status"] == "processed"
    assert result["session"]["stage"] == "submitted"
    assert result["session"]["selected_product"] == "Pure Drop Cooking Oil 2L"
    assert result["session"]["submitted_request_id"]
