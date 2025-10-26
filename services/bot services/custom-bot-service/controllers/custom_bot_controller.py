"""Controller for the custom bot service."""
from models.session_context import SessionContext
from services.tree_progression import TreeProgression
from services.node_executor import NodeExecutor
from utils.payload_validator import is_valid_payload


class CustomBotController:
    def __init__(self, tree_loader=None):
        self.tree = TreeProgression(tree_loader=tree_loader)
        self.node_executor = NodeExecutor()

    def handle(self, payload: dict, session_id: str):
        if not is_valid_payload(payload):
            raise ValueError("Invalid payload")
        session = SessionContext.load(session_id)
        next_node = self.tree.advance(session, payload)
        reply = self.node_executor.execute(next_node, session)
        return reply
