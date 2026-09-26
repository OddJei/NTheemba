"""Provider-neutral platform conversation state for Ntheemba-owned workflows."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import uuid4

from ntheemba.domain.marketplace import MarketplaceProductSearch


def _utc_now() -> datetime:
    return datetime.now(UTC)


class PlatformConversationStage(StrEnum):
    """Deterministic lifecycle for a platform-owned conversation."""

    IDLE = "idle"
    AWAITING_SELECTION = "awaiting_selection"
    HANDOFF_READY = "handoff_ready"
    BUSINESS_ACTIVE = "business_active"
    CLOSED = "closed"


@dataclass(slots=True)
class PlatformConversationSession:
    """Temporary platform workflow state, separate from tenant business sessions."""

    channel_instance_id: str
    customer_id: str
    conversation_id: str
    stage: PlatformConversationStage = PlatformConversationStage.IDLE
    search: MarketplaceProductSearch | None = None
    handoff_id: str = ""
    target_business_id: str = ""
    business_conversation_id: str = ""
    started_at: datetime = field(default_factory=_utc_now)
    last_activity_at: datetime = field(default_factory=_utc_now)
    expires_at: datetime = field(default_factory=lambda: _utc_now() + timedelta(hours=24))
    revision: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.stage, PlatformConversationStage):
            self.stage = PlatformConversationStage(self.stage)
        for name, value in {
            "channel_instance_id": self.channel_instance_id,
            "customer_id": self.customer_id,
            "conversation_id": self.conversation_id,
        }.items():
            if not value.strip():
                raise ValueError(f"{name} must not be empty")
        for name, value in {
            "started_at": self.started_at,
            "last_activity_at": self.last_activity_at,
            "expires_at": self.expires_at,
        }.items():
            if value.tzinfo is None:
                raise ValueError(f"{name} must be timezone-aware")
        if self.expires_at <= self.started_at:
            raise ValueError("expires_at must be after started_at")
        if self.revision < 0:
            raise ValueError("revision must not be negative")
        self._validate_stage()

    @classmethod
    def create(
        cls,
        channel_instance_id: str,
        customer_id: str,
        *,
        conversation_id: str | None = None,
        now: datetime | None = None,
        ttl: timedelta = timedelta(hours=24),
    ) -> PlatformConversationSession:
        moment = now or _utc_now()
        if moment.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        if ttl <= timedelta(0):
            raise ValueError("ttl must be greater than zero")
        return cls(
            channel_instance_id=channel_instance_id,
            customer_id=customer_id,
            conversation_id=conversation_id or f"PCONV-{uuid4()}",
            started_at=moment,
            last_activity_at=moment,
            expires_at=moment + ttl,
        )

    def set_search(self, search: MarketplaceProductSearch) -> None:
        if search.source_channel_id != self.channel_instance_id:
            raise ValueError("Marketplace search belongs to another platform channel")
        if not search.offers:
            self.stage = PlatformConversationStage.IDLE
            self.search = search
            self.handoff_id = ""
            self.target_business_id = ""
            self.business_conversation_id = ""
            return
        self.stage = PlatformConversationStage.AWAITING_SELECTION
        self.search = search
        self.handoff_id = ""
        self.target_business_id = ""
        self.business_conversation_id = ""

    def mark_handoff_ready(self, *, handoff_id: str, target_business_id: str) -> None:
        if self.stage is not PlatformConversationStage.AWAITING_SELECTION or self.search is None:
            raise ValueError("Marketplace selection requires an active search")
        if not handoff_id.strip() or not target_business_id.strip():
            raise ValueError("handoff_id and target_business_id are required")
        self.stage = PlatformConversationStage.HANDOFF_READY
        self.handoff_id = handoff_id.strip()
        self.target_business_id = target_business_id.strip()
        self.business_conversation_id = ""

    def activate_business(self, *, business_id: str, conversation_id: str) -> None:
        if self.stage not in {
            PlatformConversationStage.HANDOFF_READY,
            PlatformConversationStage.BUSINESS_ACTIVE,
        }:
            raise ValueError("business activation requires a ready Marketplace handoff")
        if self.target_business_id != business_id:
            raise ValueError("business activation target does not match selected handoff")
        if not conversation_id.strip():
            raise ValueError("business conversation_id is required")
        self.stage = PlatformConversationStage.BUSINESS_ACTIVE
        self.business_conversation_id = conversation_id.strip()

    def deactivate_business(self) -> None:
        """Return a stale business-active session to its consumed handoff boundary."""

        if self.stage is not PlatformConversationStage.BUSINESS_ACTIVE:
            raise ValueError("only a business-active platform session can be deactivated")
        if not self.handoff_id or not self.target_business_id:
            raise ValueError("business-active platform session is missing handoff state")
        self.stage = PlatformConversationStage.HANDOFF_READY
        self.business_conversation_id = ""

    def reset_marketplace(self) -> None:
        self.stage = PlatformConversationStage.IDLE
        self.search = None
        self.handoff_id = ""
        self.target_business_id = ""
        self.business_conversation_id = ""

    def close(self) -> None:
        self.stage = PlatformConversationStage.CLOSED
        self.search = None
        self.handoff_id = ""
        self.target_business_id = ""
        self.business_conversation_id = ""

    def touch(self, *, now: datetime | None = None, ttl: timedelta | None = None) -> None:
        moment = now or _utc_now()
        if moment.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        if moment < self.last_activity_at:
            raise ValueError("last_activity_at cannot move backwards")
        self.last_activity_at = moment
        if ttl is not None:
            if ttl <= timedelta(0):
                raise ValueError("ttl must be greater than zero")
            self.expires_at = moment + ttl

    def expired(self, *, now: datetime | None = None) -> bool:
        moment = now or _utc_now()
        if moment.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        return moment >= self.expires_at

    def copy_with_revision(self, revision: int) -> PlatformConversationSession:
        if revision < 0:
            raise ValueError("revision must not be negative")
        return replace(self, revision=revision)

    def _validate_stage(self) -> None:
        if self.stage is PlatformConversationStage.AWAITING_SELECTION and self.search is None:
            raise ValueError("awaiting selection requires Marketplace search state")
        if self.stage in {
            PlatformConversationStage.HANDOFF_READY,
            PlatformConversationStage.BUSINESS_ACTIVE,
        }:
            if not self.handoff_id or not self.target_business_id:
                raise ValueError("handoff stages require handoff and target business")
        if (
            self.stage is PlatformConversationStage.BUSINESS_ACTIVE
            and not self.business_conversation_id
        ):
            raise ValueError("business-active platform session requires business conversation ID")
        if self.stage is PlatformConversationStage.CLOSED and any(
            (
                self.search is not None,
                self.handoff_id,
                self.target_business_id,
                self.business_conversation_id,
            )
        ):
            raise ValueError("closed platform sessions cannot retain active workflow state")
