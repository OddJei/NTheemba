"""Execute a node and return a reply for custom bot."""

from models.node import Node
from models.session_context import SessionContext


class NodeExecutor:
    def execute(self, node: Node, session: SessionContext) -> dict:
        return {"reply": f"Executed node {getattr(node, 'node_id', 'unknown')}", "session": getattr(session, 'session_id', None)}
