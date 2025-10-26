import pytest
from datetime import datetime

from models.node import NodeDefinition, NodeTransition, NodeHandler, NodeType, NodeValidation, ValidationRule, IntentTree


def make_node(name):
    handler = NodeHandler(handler_function="fn", handler_module="handlers.test", required_params=[], optional_params=[])
    return NodeDefinition(node_name=name, node_type=NodeType.ACTION, description=f"{name}", handler=handler)


def test_intent_tree_path_and_validation():
    # Create nodes A -> B -> C
    a = make_node("A")
    b = make_node("B")
    c = make_node("C")

    # transitions
    t_ab = NodeTransition(from_node="A", to_node="B", condition=None)
    t_bc = NodeTransition(from_node="B", to_node="C", condition=None)

    a.allowed_transitions = [t_ab]
    b.allowed_transitions = [t_bc]

    nodes = {"A": a, "B": b, "C": c}
    tree = IntentTree(tree_name="t", root_node="A", nodes=nodes, description="test")

    path = tree.get_tree_path("A", "C")
    assert path == ["A", "B", "C"]

    # validate tree should return no errors
    assert tree.validate_tree() == []

