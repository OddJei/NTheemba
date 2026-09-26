"""HTTP tests for the Phase 11.11 developer conversation simulator."""

from __future__ import annotations

from fastapi.testclient import TestClient
from ntheemba.config import Settings
from ntheemba.main import create_app


def _message(
    text: str,
    *,
    message_id: str = "sim-message-1",
    request_id: str = "sim-request-1",
    business_id: str = "harvest-big-shop",
    customer_id: str = "260970000001",
) -> dict[str, str]:
    return {
        "business_id": business_id,
        "customer_id": customer_id,
        "message_id": message_id,
        "request_id": request_id,
        "text": text,
    }


def test_simulator_console_is_protected_self_contained_ui(client: TestClient) -> None:
    response = client.get("/dev/simulator")

    assert response.status_code == 200
    assert "Ntheemba Conversation Simulator" in response.text
    assert "Message pipeline" in response.text
    assert "Session inspector" in response.text
    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "unsafe-inline" not in response.headers["content-security-policy"]


def test_lists_seeded_business_scenarios(client: TestClient) -> None:
    response = client.get("/dev/simulator/businesses")

    assert response.status_code == 200
    payload = response.json()
    assert [item["business_id"] for item in payload] == [
        "harvest-big-shop",
        "serahs-glow-lounge",
    ]
    assert "Show me cooking oil" in payload[0]["suggested_messages"]


def test_message_runs_real_pipeline_and_returns_reply_session_and_trace(
    client: TestClient,
) -> None:
    response = client.post(
        "/dev/simulator/messages",
        json=_message("What time do you close?"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "processed"
    assert payload["trace_id"].startswith("TRACE-")
    assert payload["conversation_id"].startswith("CONV-")
    reply_text = payload["replies"][0]["text"]
    assert (
        "closes at" in reply_text
        or "The business is currently closed. Hours for" in reply_text
    )
    assert payload["session"]["revision"] == 1
    assert payload["session"]["history"][0]["role"] == "customer"

    trace = client.get("/dev/simulator/requests/sim-request-1/trace")
    assert trace.status_code == 200
    nodes = {event["node_id"] for event in trace.json()}
    assert {
        "message.process",
        "message.deduplicate",
        "session.open",
        "message.interpret",
        "workflow.route",
        "transition.validate",
        "workflow.execute",
        "session.commit",
        "reply.publish",
    } <= nodes


def test_order_use_case_preserves_state_across_messages(client: TestClient) -> None:
    messages = (
        "Show me cooking oil",
        "1",
        "Order this",
        "2",
        "delivery",
        "Mufulira Central near the post office",
        "James +260970000001",
        "confirm",
    )
    payload: dict[str, object] = {}
    for index, text in enumerate(messages, start=1):
        response = client.post(
            "/dev/simulator/messages",
            json=_message(
                text,
                message_id=f"order-message-{index}",
                request_id=f"order-request-{index}",
            ),
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "processed"

    session = payload["session"]
    assert isinstance(session, dict)
    assert session["flow"] == "order"
    assert session["stage"] == "submitted"
    assert session["selected_product"] == "Pure Drop Cooking Oil 2L"
    assert session["quantity"] == 2
    assert session["submitted_request_id"].startswith("ORD-")



def test_booking_use_case_preserves_state_across_messages(client: TestClient) -> None:
    businesses = client.get("/dev/simulator/businesses").json()
    booking_date = businesses[1]["suggested_messages"][2]
    messages = (
        "I want to book an appointment",
        "1",
        booking_date,
        "1",
        "anyone",
        "James +260970000001",
        "confirm",
    )
    payload: dict[str, object] = {}
    for index, text in enumerate(messages, start=1):
        response = client.post(
            "/dev/simulator/messages",
            json=_message(
                text,
                message_id=f"booking-message-{index}",
                request_id=f"booking-request-{index}",
                business_id="serahs-glow-lounge",
                customer_id="260970000002",
            ),
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "processed"

    session = payload["session"]
    assert isinstance(session, dict)
    assert session["flow"] == "booking"
    assert session["stage"] == "submitted"
    assert session["selected_service"] == "Gel Nails"
    assert session["selected_date"] == booking_date
    assert session["submitted_request_id"].startswith("BKG-")

def test_replay_same_message_id_exercises_deduplication(client: TestClient) -> None:
    first = client.post(
        "/dev/simulator/messages",
        json=_message("What time do you close?"),
    )
    assert first.json()["status"] == "processed"

    replay = client.post(
        "/dev/simulator/conversations/harvest-big-shop/260970000001/replay",
        json={"same_message_id": True},
    )

    assert replay.status_code == 200
    payload = replay.json()
    assert payload["status"] == "duplicate"
    assert payload["replies"] == []
    trace = client.get(f"/dev/simulator/requests/{payload['request_id']}/trace").json()
    final_nodes = {event["node_id"] for event in trace}
    assert "message.deduplicate" in final_nodes
    assert "session.open" not in final_nodes


def test_reset_releases_simulator_message_ids(client: TestClient) -> None:
    original = _message("What time do you close?")
    assert client.post("/dev/simulator/messages", json=original).json()["status"] == "processed"

    reset = client.delete(
        "/dev/simulator/conversations/harvest-big-shop/260970000001"
    )
    assert reset.status_code == 204
    empty = client.get(
        "/dev/simulator/conversations/harvest-big-shop/260970000001"
    ).json()
    assert empty["exists"] is False

    retried = client.post("/dev/simulator/messages", json=original)
    assert retried.json()["status"] == "processed"


def test_fake_dependency_controls_affect_real_simulated_pipeline(client: TestClient) -> None:
    configured = client.put(
        "/dev/dependencies/publisher",
        json={
            "fail_next": 1,
            "operations": ["publish_many"],
            "failure_message": "simulated gateway outage",
        },
    )
    assert configured.status_code == 200

    response = client.post(
        "/dev/simulator/messages",
        json=_message("What time do you close?"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["error_code"] == "INFRASTRUCTURE_FAILED"
    trace = client.get("/dev/simulator/requests/sim-request-1/trace").json()
    failed = [event for event in trace if event["status"] == "failed"]
    assert any(event["node_id"] == "reply.publish" for event in failed)


def test_simulator_is_not_registered_outside_developer_environments() -> None:
    app = create_app(
        Settings(
            environment="production",
            dev_tools_enabled=True,
            docs_enabled=False,
            trace_export_enabled=False,
        )
    )
    with TestClient(app) as client:
        assert client.get("/dev/simulator").status_code == 404
        assert client.get("/dev/simulator/businesses").status_code == 404

    assert not hasattr(app.state, "conversation_simulator")


def test_simulator_exposes_safe_audit_trail_for_pipeline_debugging(client: TestClient) -> None:
    response = client.post(
        "/dev/simulator/messages",
        json=_message(
            "What time do you close?",
            message_id="audit-message-1",
            request_id="audit-request-1",
        ),
    )
    assert response.status_code == 200

    audit = client.get("/dev/simulator/audit")
    assert audit.status_code == 200
    events = [
        event for event in audit.json() if event["request_id"] == "audit-request-1"
    ]
    assert events
    assert events[0]["event_id"].startswith("AUD-")
    assert all("api_token" not in str(event["data"]).lower() for event in events)
    assert any(event["event_type"] == "message.processed" for event in events)
