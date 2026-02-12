"""Payload dataclass for custom bot."""

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class Payload:
    type: str
    data: Dict[str, Any]
