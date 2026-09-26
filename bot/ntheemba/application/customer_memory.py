"""Consent-aware recording of minimal customer and conversation memory."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from ntheemba.application.service import ProcessMessageCommand
from ntheemba.application.workflow_router import WorkflowResult
from ntheemba.domain.customer_memory import (
    ConsentType,
    ConversationMessage,
    ConversationSummary,
    CustomerAddress,
    CustomerConsent,
    CustomerPreference,
    CustomerQuestion,
    QuestionOutcome,
)
from ntheemba.domain.enums import IntentType
from ntheemba.domain.intents import Intent
from ntheemba.domain.session import Session
from ntheemba.ports.customer_memory import CustomerMemoryRepository


class InteractionRecorder(Protocol):
    async def record_success(
        self,
        *,
        command: ProcessMessageCommand,
        session: Session,
        intent: Intent,
        result: WorkflowResult,
        published_message_ids: tuple[str, ...],
    ) -> None: ...


class CustomerMemoryService:
    """Persist only consented raw details plus small business-scoped summaries."""

    def __init__(self, repository: CustomerMemoryRepository) -> None:
        self.repository = repository

    async def set_consent(
        self,
        customer_id: str,
        consent_type: ConsentType,
        granted: bool,
        *,
        source: str,
    ) -> CustomerConsent:
        return await self.repository.save_consent(
            CustomerConsent(customer_id, consent_type, granted, source)
        )

    async def is_allowed(self, customer_id: str, consent_type: ConsentType) -> bool:
        consent = await self.repository.get_consent(customer_id, consent_type.value)
        return bool(consent and consent.granted)

    async def record_success(
        self,
        *,
        command: ProcessMessageCommand,
        session: Session,
        intent: Intent,
        result: WorkflowResult,
        published_message_ids: tuple[str, ...],
    ) -> None:
        await self._record_summary(command, session, intent, result)
        if await self.is_allowed(command.customer_id, ConsentType.MESSAGE_RETENTION):
            await self._record_raw_messages(
                command, session, result, published_message_ids
            )
            await self._record_question(command, session, intent, result)
        if await self.is_allowed(command.customer_id, ConsentType.SAVED_CHECKOUT):
            await self._record_checkout(command, session)

    async def _record_raw_messages(
        self,
        command: ProcessMessageCommand,
        session: Session,
        result: WorkflowResult,
        published_message_ids: tuple[str, ...],
    ) -> None:
        await self.repository.record_message(
            ConversationMessage(
                command.message_id,
                session.conversation_id,
                command.business_id,
                command.customer_id,
                "customer",
                command.text,
                command.received_at or datetime.now(UTC),
            )
        )
        for message_id, reply in zip(published_message_ids, result.replies, strict=False):
            text = reply.text or reply.caption
            if text:
                await self.repository.record_message(
                    ConversationMessage(
                        message_id,
                        session.conversation_id,
                        command.business_id,
                        command.customer_id,
                        "assistant",
                        text,
                    )
                )

    async def _record_summary(
        self,
        command: ProcessMessageCommand,
        session: Session,
        intent: Intent,
        result: WorkflowResult,
    ) -> None:
        event_types = tuple(event.event_type for event in result.events)
        outcome = "completed" if result.close_session or session.stage.value == "submitted" else "continued"
        await self.repository.record_summary(
            ConversationSummary(
                summary_id=f"SUM-{uuid4()}",
                conversation_id=session.conversation_id,
                business_id=command.business_id,
                customer_id=command.customer_id,
                intent=intent.type.value,
                outcome=outcome,
                topic=intent.type.value,
                follow_up_required=not result.close_session,
                summary={
                    "flow": session.flow.value,
                    "stage": session.stage.value,
                    "events": event_types,
                    "reply_count": len(result.replies),
                },
            )
        )

    async def _record_question(
        self,
        command: ProcessMessageCommand,
        session: Session,
        intent: Intent,
        result: WorkflowResult,
    ) -> None:
        if intent.type not in {
            IntentType.BUSINESS_INFO,
            IntentType.BUSINESS_HOURS,
            IntentType.FAQ,
            IntentType.LOYALTY_STATUS,
        }:
            return
        events = {event.event_type for event in result.events}
        if any("handover" in event for event in events):
            outcome = QuestionOutcome.HANDED_OVER
        elif any("not_found" in event or "denied" in event for event in events):
            outcome = QuestionOutcome.UNRESOLVED
        elif any("failed" in event for event in events):
            outcome = QuestionOutcome.PARTIAL
        else:
            outcome = QuestionOutcome.ANSWERED
        await self.repository.record_question(
            CustomerQuestion(
                question_id=f"Q-{uuid4()}",
                business_id=command.business_id,
                customer_id=command.customer_id,
                conversation_id=session.conversation_id,
                topic=intent.type.value,
                question_text=command.text[:500],
                outcome=outcome,
                required_handover=outcome == QuestionOutcome.HANDED_OVER,
            )
        )

    async def _record_checkout(
        self,
        command: ProcessMessageCommand,
        session: Session,
    ) -> None:
        draft = session.order_draft
        if draft is None:
            return
        if draft.delivery_details:
            existing = await self.repository.list_addresses(
                command.customer_id,
                business_id=command.business_id,
            )
            if draft.delivery_details.casefold() not in {
                item.location_text.casefold() for item in existing
            }:
                await self.repository.save_address(
                    CustomerAddress(
                        address_id=f"ADDR-{uuid4()}",
                        customer_id=command.customer_id,
                        business_id=command.business_id,
                        label="Saved delivery",
                        location_text=draft.delivery_details,
                        is_default=True,
                    )
                )
        if draft.fulfilment_method is not None:
            await self.repository.save_preference(
                CustomerPreference(
                    preference_id=f"PREF-{uuid4()}",
                    customer_id=command.customer_id,
                    business_id=command.business_id,
                    key="preferred_fulfilment",
                    value={"method": draft.fulfilment_method.value},
                    source="confirmed_order",
                )
            )
