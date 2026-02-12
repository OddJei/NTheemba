from utils.payload_validator import PayloadValidator
from utils.node_validator import NodeValidator


def test_payload_validator_basic():
    pv = PayloadValidator()
    valid, errors = pv.validate_payload({
        "request_id": "r1",
        "message": "hi",
        "to": "me",
        "from": "you",
        "meta": {
            "platform": "wa",
            "bot": {},
            "user": {"role": "public"},
            "session": {"session_id": "s1", "session_mode": "public", "bot_type": "default"},
            "current_event": {"event_id": "e1", "timestamp": "t", "status": "pending", "current_node": "root"}
        }
    })
    assert valid


def test_node_validator_stub():
    nv = NodeValidator()
    # create minimal NodeDefinition-like object
    class N:
        def __init__(self):
            self.node_name = "n"
            # create a transition-like object that matches expected interface
            self.allowed_transitions = [type("T", (), {"to_node": "n"})()]
            self.validation_rules = []

    n = N()
    # Since no transitions and no rules, validation should succeed when comparing same node
    ok, errors = nv.validate_transition(n, n, current_data={})
    assert ok
