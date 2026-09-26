"""Deterministic router for Ntheemba-owned platform workflows."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ntheemba.application.marketplace import (
    MarketplaceHandoffConsumptionService,
    MarketplaceHandoffService,
    MarketplaceProductDiscoveryService,
    MarketplaceSelectionError,
    require_marketplace_context,
)
from ntheemba.domain.business import (
    ChannelRole,
    ChannelScope,
    PlatformCapability,
    ResolvedPlatformContext,
)
from ntheemba.domain.marketplace import MarketplaceBusinessHandoffContext
from ntheemba.domain.platform_session import PlatformConversationSession, PlatformConversationStage
from ntheemba.domain.product_resolution import ProductQuery
from ntheemba.application.workflow_router import WorkflowReply


class PlatformWorkflowAction(StrEnum):
    """High-level result produced by the deterministic platform router."""

    REPLIED = "replied"
    BUSINESS_ENTRY_READY = "business_entry_ready"
    BUSINESS_CONTINUE = "business_continue"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class PlatformWorkflowResult:
    """Reply and optional trusted business transition produced by platform routing."""

    action: PlatformWorkflowAction
    replies: tuple[WorkflowReply, ...] = ()
    business_context: MarketplaceBusinessHandoffContext | None = None


class PlatformWorkflowRouter:
    """Route platform text through deterministic Marketplace state only."""

    _RESET_TERMS = frozenset({"marketplace", "start over", "search again", "new search"})
    _CONTINUE_TERMS = frozenset(
        {"continue", "proceed", "yes", "buy", "order", "go ahead", "choose this"}
    )
    _CANCEL_TERMS = frozenset({"cancel", "back", "go back", "stop"})
    _CLOSE_TERMS = frozenset({"close", "close chat", "end conversation"})

    def __init__(
        self,
        *,
        discovery: MarketplaceProductDiscoveryService,
        handoff: MarketplaceHandoffService,
        consumption: MarketplaceHandoffConsumptionService,
    ) -> None:
        self.discovery = discovery
        self.handoff = handoff
        self.consumption = consumption

    async def route(
        self,
        context: ResolvedPlatformContext,
        session: PlatformConversationSession,
        text: str,
    ) -> PlatformWorkflowResult:
        if context.channel.scope is not ChannelScope.PLATFORM:
            raise MarketplaceSelectionError("platform workflow routing requires PLATFORM context")
        if session.channel_instance_id != context.channel.channel_instance_id:
            raise MarketplaceSelectionError("platform session belongs to another channel")
        if context.role is not ChannelRole.MARKETPLACE:
            return self._reply(
                "This Ntheemba platform channel does not have an active deterministic "
                "workflow yet."
            )
        require_marketplace_context(context)
        if PlatformCapability.MARKETPLACE not in context.capabilities:
            raise MarketplaceSelectionError(
                "Marketplace capability is not enabled for this channel"
            )
        cleaned = " ".join(text.strip().split())
        if not cleaned:
            return self._reply("Tell me what product you want to find in Marketplace.")
        normalized = cleaned.casefold()

        if normalized in self._CLOSE_TERMS:
            session.close()
            return PlatformWorkflowResult(
                PlatformWorkflowAction.CLOSED,
                (WorkflowReply.text_reply("Marketplace conversation closed."),),
            )
        if normalized in self._RESET_TERMS:
            session.reset_marketplace()
            return self._reply("What product would you like me to find in Marketplace?")
        if normalized in self._CANCEL_TERMS:
            session.reset_marketplace()
            return self._reply("Okay. What would you like to search for instead?")

        if session.stage is PlatformConversationStage.IDLE:
            return await self._search(context, session, cleaned)
        if session.stage is PlatformConversationStage.AWAITING_SELECTION:
            if self._looks_like_new_search(normalized):
                return await self._search(context, session, self._strip_search_prefix(cleaned))
            return await self._select(context, session, cleaned)
        if session.stage is PlatformConversationStage.HANDOFF_READY:
            if normalized not in self._CONTINUE_TERMS:
                return self._reply(
                    "Reply 'continue' to enter the selected business, or 'search again' "
                    "to choose something else."
                )
            try:
                business_context = await self.consumption.consume(context, session.handoff_id)
            except MarketplaceSelectionError:
                session.reset_marketplace()
                return self._reply(
                    "That Marketplace selection changed before handoff. "
                    "Please search again."
                )
            return PlatformWorkflowResult(
                PlatformWorkflowAction.BUSINESS_ENTRY_READY,
                (
                    WorkflowReply.text_reply(
                        f"Connecting you to {business_context.business.display_name} for the "
                        "selected product."
                    ),
                ),
                business_context=business_context,
            )
        if session.stage is PlatformConversationStage.BUSINESS_ACTIVE:
            return PlatformWorkflowResult(PlatformWorkflowAction.BUSINESS_CONTINUE)
        return self._reply("This Marketplace session is no longer active.")

    async def _search(
        self,
        context: ResolvedPlatformContext,
        session: PlatformConversationSession,
        raw_query: str,
    ) -> PlatformWorkflowResult:
        query_text = self._strip_search_prefix(raw_query).strip()
        if not query_text:
            return self._reply("Tell me the product name you want to find.")
        search = await self.discovery.search(context, ProductQuery(query_text))
        session.set_search(search)
        if not search.offers:
            return self._reply(
                "I couldn't find a trusted Marketplace match for that product. "
                "Try another product name."
            )
        lines = ["I found these Marketplace options:"]
        for index, offer in enumerate(search.offers, start=1):
            shop = f" · {offer.shop_id}" if offer.shop_id else ""
            lines.append(
                f"{index}. {offer.name} — {offer.business_name} — "
                f"{offer.currency} {offer.selling_price}{shop}"
            )
        lines.append("Reply with the option number you want.")
        return self._reply("\n".join(lines))

    async def _select(
        self,
        context: ResolvedPlatformContext,
        session: PlatformConversationSession,
        selection_text: str,
    ) -> PlatformWorkflowResult:
        if session.search is None:
            session.reset_marketplace()
            return self._reply("That search is no longer available. Tell me what to find again.")
        selection: str | int = selection_text
        if selection_text.isdigit():
            selection = int(selection_text)
        try:
            handoff_context = await self.handoff.select(
                context,
                session.search,
                selection,
            )
        except MarketplaceSelectionError:
            return self._reply(
                "That option is not available. Reply with one of the listed numbers."
            )
        session.mark_handoff_ready(
            handoff_id=handoff_context.handoff.handoff_id,
            target_business_id=handoff_context.business.business_id,
        )
        return self._reply(
            f"You selected {handoff_context.handoff.product_name} from "
            f"{handoff_context.business.display_name}. Reply 'continue' to proceed."
        )

    @staticmethod
    def _reply(text: str) -> PlatformWorkflowResult:
        return PlatformWorkflowResult(
            PlatformWorkflowAction.REPLIED,
            (WorkflowReply.text_reply(text),),
        )

    @staticmethod
    def _looks_like_new_search(normalized: str) -> bool:
        return normalized.startswith(("search ", "find ", "looking for "))

    @staticmethod
    def _strip_search_prefix(text: str) -> str:
        cleaned = text.strip()
        lowered = cleaned.casefold()
        for prefix in ("search for ", "search ", "find ", "looking for "):
            if lowered.startswith(prefix):
                return cleaned[len(prefix) :]
        return cleaned
