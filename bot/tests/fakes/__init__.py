"""In-memory test doubles for all Phase 2 ports."""

from tests.fakes.application import RecordingWorkflowHandler, StubInterpreter
from tests.fakes.audit import InMemoryAuditSink
from tests.fakes.ncpc import InMemoryNCPC
from tests.fakes.publisher import InMemoryOutgoingPublisher
from tests.fakes.sessions import (
    InMemoryDeduplicationStore,
    InMemorySessionLockManager,
    InMemorySessionRepository,
)
from tests.fakes.tradeflow import InMemoryTradeFlow

__all__ = [
    "InMemoryAuditSink",
    "InMemoryDeduplicationStore",
    "InMemoryNCPC",
    "InMemoryOutgoingPublisher",
    "InMemorySessionLockManager",
    "InMemorySessionRepository",
    "InMemoryTradeFlow",
    "RecordingWorkflowHandler",
    "StubInterpreter",
]
