import types
from models.node import NodeDefinition, NodeHandler, NodeType
from models.session_context import SessionContext, UserContext, TreeState, NodeState, NodeStatus, SessionStatus
from services.node_executor import NodeExecutor


class FakeRedis:
    def update_session(self, session):
        return True
    def _store_tree_state(self, session_id, tree_state):
        return True


class FakeTreeSelector:
    def _extract_intent_feature(self, payload):
        return "product_management"


def make_node(name):
    handler = NodeHandler(handler_function="dummy", handler_module="tests.dummy_handlers", required_params=[], optional_params=[])
    return NodeDefinition(node_name=name, node_type=NodeType.ACTION, description=name, handler=handler)


def test_node_executor_routes_to_missing_handler(monkeypatch):
    # Create session
    session = SessionContext(
        session_id="s1",
        user_id=None,
        status=SessionStatus.ACTIVE,
        created_at=__import__('datetime').datetime.now(),
        last_activity=__import__('datetime').datetime.now(),
        expires_at=__import__('datetime').datetime.now(),
        user_context=UserContext()
    )

    node = make_node("n1")
    exec = NodeExecutor(redis_client=FakeRedis(), tree_selector=FakeTreeSelector())
    success, data, errors = exec.execute(node, session, payload={})
    # There is no handler module tests.dummy_handlers, so expect failure about handler module
    assert not success
    assert errors
