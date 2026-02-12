"""Node validator for custom bot."""

from models.node import Node


def validate_node(node: Node) -> bool:
    return hasattr(node, 'node_id')
