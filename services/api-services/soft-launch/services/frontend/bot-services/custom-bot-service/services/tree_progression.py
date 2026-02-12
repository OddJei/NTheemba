"""Tree progression for custom bot (mirrors default implementation)."""

from models.node import Node
from models.session_context import SessionContext


class TreeProgression:
    def __init__(self, tree_loader=None):
        self.tree_loader = tree_loader
        self.root = self._load_tree()

    def _load_tree(self):
        if callable(self.tree_loader):
            return self.tree_loader()
        return Node(node_id="root", data={})

    def advance(self, session: SessionContext, payload: dict):
        return self.root
