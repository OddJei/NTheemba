"""Node model for custom bot."""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class Node:
    node_id: str
    data: Dict[str, Any] = field(default_factory=dict)
    children: List['Node'] = field(default_factory=list)

    def find_child(self, predicate) -> 'Node':
        for c in self.children:
            if predicate(c):
                return c
        return None
