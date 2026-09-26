"""Style-only reply localization with protected-fact preservation."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from ntheemba.application.workflow_router import WorkflowReply, WorkflowReplyType

_MONEY_PATTERN = re.compile(
    r"(?<!\w)(?:K|R|\$|ZMW\s+|USD\s+|EUR\s+|GBP\s+|ZAR\s+)?\d[\d,]*(?:\.\d{2})?(?!\w)"
)
_DATE_PATTERN = re.compile(r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2} [A-Z][a-z]{2} \d{4})\b")
_TIME_PATTERN = re.compile(r"\b\d{1,2}:\d{2}(?:-\d{1,2}:\d{2})?\b")
_REQUEST_PATTERN = re.compile(r"\b[A-Z]{2,}(?:-[A-Z0-9]+)+\b")
_PHONE_PATTERN = re.compile(r"\+?\d[\d\s-]{6,20}\d")
_COMMAND_PATTERN = re.compile(r"\b(?:YES|CONFIRM|CORRECT|CANCEL|SKIP)\b")
_LABEL_VALUE_PATTERN = re.compile(
    r"^(?:Product|Service|Name|Contact|Date|Time|Staff|Fulfilment|Delivery):\s*(.+)$",
    re.MULTILINE,
)
_NUMBERED_ITEM_PATTERN = re.compile(r"^\d+\.\s+(.+?)(?:\s+[—-]\s+|\s+\(|$)", re.MULTILINE)

_HIGH_RISK_RESPONSE_TYPES = frozenset(
    {
        "order_review",
        "order_price_changed",
        "order_submitted",
        "booking_review",
        "booking_price_changed",
        "booking_submitted",
        "quantity_unavailable",
        "dependency_failure",
        "generic_failure",
        "handover_requested",
        "human_active",
        "conversation_closed",
    }
)


class ReplyTextProvider(Protocol):
    """Source of style-only rewritten reply text."""

    async def propose_text(
        self,
        *,
        text: str,
        response_type: str,
        blend: float,
        languages: tuple[str, ...],
        protected_terms: tuple[str, ...],
    ) -> str:
        """Return a localized text proposal."""


@dataclass(frozen=True, slots=True)
class ReplyLocalizationConfig:
    """Runtime policy for advisory local-language reply construction."""

    enabled: bool = False
    blend: float = 0.15
    languages: tuple[str, ...] = ("bemba", "nyanja")
    max_text_length: int = 3500

    def __post_init__(self) -> None:
        if not 0.10 <= self.blend <= 0.20:
            raise ValueError("blend must be between 0.10 and 0.20")
        if not self.languages:
            raise ValueError("languages must not be empty")
        if self.max_text_length < 200:
            raise ValueError("max_text_length must be at least 200")


class SafeReplyLocalizer:
    """Rewrite only safe text replies and fall back on any validation failure."""

    def __init__(
        self,
        *,
        provider: ReplyTextProvider,
        config: ReplyLocalizationConfig,
    ) -> None:
        self._provider = provider
        self._config = config

    async def localize_many(
        self,
        replies: tuple[WorkflowReply, ...],
    ) -> tuple[WorkflowReply, ...]:
        """Return localized replies where safe, preserving tuple shape and metadata."""

        if not self._config.enabled or not replies:
            return replies
        localized: list[WorkflowReply] = []
        for reply in replies:
            localized.append(await self.localize(reply))
        return tuple(localized)

    async def localize(self, reply: WorkflowReply) -> WorkflowReply:
        """Localize one text reply or return the original reply unchanged."""

        if reply.kind != WorkflowReplyType.TEXT or reply.text is None:
            return reply
        response_type = _response_type(reply.metadata)
        if response_type in _HIGH_RISK_RESPONSE_TYPES:
            return reply
        protected_terms = protected_terms_for(reply.text)
        try:
            candidate = await self._provider.propose_text(
                text=reply.text,
                response_type=response_type,
                blend=self._config.blend,
                languages=self._config.languages,
                protected_terms=protected_terms,
            )
        except Exception:
            return reply
        if not self._valid_candidate(
            original=reply.text,
            candidate=candidate,
            protected_terms=protected_terms,
        ):
            return reply
        return WorkflowReply.text_reply(candidate.strip(), metadata=reply.metadata)

    def _valid_candidate(
        self,
        *,
        original: str,
        candidate: str,
        protected_terms: tuple[str, ...],
    ) -> bool:
        cleaned = candidate.strip()
        if not cleaned:
            return False
        if len(cleaned) > min(self._config.max_text_length, max(len(original) * 2, 200)):
            return False
        return all(term in cleaned for term in protected_terms)


def protected_terms_for(text: str) -> tuple[str, ...]:
    """Extract facts and commands that a model rewrite must keep verbatim."""

    terms: list[str] = []
    for pattern in (
        _MONEY_PATTERN,
        _DATE_PATTERN,
        _TIME_PATTERN,
        _REQUEST_PATTERN,
        _PHONE_PATTERN,
        _COMMAND_PATTERN,
        _LABEL_VALUE_PATTERN,
        _NUMBERED_ITEM_PATTERN,
    ):
        for match in pattern.finditer(text):
            value = match.group(1) if match.lastindex else match.group(0)
            cleaned = value.strip(" .,:;")
            if cleaned and len(cleaned) <= 120:
                terms.append(cleaned)
    return tuple(dict.fromkeys(terms))


def _response_type(metadata: Mapping[str, object]) -> str:
    value = metadata.get("response_type")
    return str(value).strip() if value is not None else ""
