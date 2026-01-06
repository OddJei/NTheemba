from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping, Optional


Headers = Dict[str, str]
Json = Dict[str, Any]


@dataclass(frozen=True)
class OperationSpec:
    service: str
    method: str
    path: str


@dataclass
class Request:
    service: str
    operation: str
    method: str
    path: str
    query: Optional[Mapping[str, str]] = None
    headers: Headers = field(default_factory=dict)
    body: Optional[Json] = None
    timeout: float = 10.0
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Response:
    status: int
    headers: Mapping[str, str]
    body: Any


NextCall = Callable[[Request], "Any"]
