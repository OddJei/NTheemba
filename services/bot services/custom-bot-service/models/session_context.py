"""Session context model for custom bot."""

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class SessionContext:
    session_id: str
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, session_id: str) -> 'SessionContext':
        return SessionContext(session_id=session_id)

    def save(self):
        return True
