"""Tree loader helper for custom bot."""
from models.node import Node
import json


def load_tree_from_json(path: str) -> Node:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    def build(node_dict):
        n = Node(node_id=node_dict.get('id', 'unknown'), data=node_dict.get('data', {}))
        for c in node_dict.get('children', []):
            n.children.append(build(c))
        return n

    return build(data)
