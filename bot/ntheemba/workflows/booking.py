"""Service booking workflow with live slot validation and idempotent submission."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time

from ntheemba.application.workflow_router import (
    WorkflowContext,
    WorkflowEvent,
    WorkflowHandler,
    WorkflowReply,
    WorkflowResult,
)
from ntheemba.domain.booking_draft import (
    AppointmentSlot,
    BookingDraft,
    BookingStaffOption,
    ServiceSelection,
)
from ntheemba.domain.enums import Flow, IntentType, Stage
from ntheemba.domain.intents import PendingQuestion
from ntheemba.domain.session import Session
from ntheemba.domain.transitions import TransitionPolicy
from ntheemba.ports.tradeflow import (
    BookingSubmissionRequest,
    StaffOption,
    SubmissionResult,
    TradeFlowPort,
)
from ntheemba.services.response_builder import ResponseBuilder

_GENERIC_BOOKING_TERMS = frozenset(
    {"appointment", "book", "booking", "please", "schedule", "service", "want"}
)
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_SUPPORTED_INTENTS = frozenset(
    {
        IntentType.START_BOOKING,
        IntentType.SELECT_ITEM,
        IntentType.PROVIDE_DATE,
        IntentType.SELECT_TIME,
        IntentType.SELECT_STAFF,
        IntentType.PROVIDE_CUSTOMER_DETAILS,
        IntentType.CONFIRM,
        IntentType.CORRECT,
        IntentType.CANCEL,
    }
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class BookingStateError(ValueError):
    """Raised when booking data and session stage disagree."""


class UnsupportedBookingIntentError(ValueError):
    """Raised when the booking workflow receives an intent it does not own."""


@dataclass(frozen=True, slots=True)
class BookingWorkflowConfig:
    service_search_limit: int = 10
    maximum_staff_options: int = 10

    def __post_init__(self) -> None:
        if self.service_search_limit <= 0:
            raise ValueError("service_search_limit must be greater than zero")
        if self.maximum_staff_options <= 0:
            raise ValueError("maximum_staff_options must be greater than zero")


class BookingWorkflow:
    """Collect, validate, review, and submit one booking request."""

    def __init__(
        self,
        *,
        tradeflow: TradeFlowPort,
        responses: ResponseBuilder,
        transition_policy: TransitionPolicy | None = None,
        clock: Callable[[], datetime] = _utc_now,
        config: BookingWorkflowConfig | None = None,
    ) -> None:
        self.tradeflow = tradeflow
        self.responses = responses
        self.transition_policy = transition_policy or TransitionPolicy()
        self.clock = clock
        self.config = config or BookingWorkflowConfig()

    async def handle(self, context: WorkflowContext) -> WorkflowResult:
        if context.intent.type not in _SUPPORTED_INTENTS:
            raise UnsupportedBookingIntentError(
                f"booking workflow does not handle {context.intent.type.value!r}"
            )
        try:
            handlers = {
                IntentType.START_BOOKING: self._start,
                IntentType.SELECT_ITEM: self._select_service,
                IntentType.PROVIDE_DATE: self._provide_date,
                IntentType.SELECT_TIME: self._select_time,
                IntentType.SELECT_STAFF: self._select_staff,
                IntentType.PROVIDE_CUSTOMER_DETAILS: self._provide_customer,
                IntentType.CONFIRM: self._confirm,
                IntentType.CORRECT: self._correct,
                IntentType.CANCEL: self._cancel,
            }
            return await handlers[context.intent.type](context)
        except (ConnectionError, TimeoutError) as error:
            return self._dependency_failure(error, retryable=True)
        except LookupError as error:
            return self._dependency_failure(error, retryable=False)

    async def _start(self, context: WorkflowContext) -> WorkflowResult:
        session = context.session
        if session.flow == Flow.IDLE and session.stage in {Stage.CANCELLED, Stage.RESOLVED}:
            session.transition_to(self.transition_policy, Flow.IDLE, Stage.START)
        if session.flow == Flow.IDLE:
            session.transition_to(self.transition_policy, Flow.BOOKING, Stage.SERVICE_SELECTION)
        elif session.flow != Flow.BOOKING:
            raise BookingStateError("booking can only start from idle or booking flow")
        session.booking_draft = BookingDraft()
        query = self._service_query(
            context.intent.entities.query or context.intent.entities.raw_text
        )
        if not query:
            self._ask(session, Stage.SERVICE_SELECTION, IntentType.SELECT_ITEM, options=())
            return WorkflowResult(
                replies=(self.responses.ask_for_missing_booking_field("service"),),
                events=(WorkflowEvent(event_type="booking.started", data={"query": False}),),
            )
        services = await self.tradeflow.search_services(
            context.business_id,
            query,
            limit=self.config.service_search_limit,
        )
        draft = self._require_draft(session)
        if not services:
            self._ask(session, Stage.SERVICE_SELECTION, IntentType.SELECT_ITEM, options=())
            return WorkflowResult(
                replies=(self.responses.no_catalogue_match(item_name="service"),),
                events=(WorkflowEvent(event_type="booking.service_not_found"),),
            )
        if len(services) > 1:
            draft.set_service_candidates(services)
            options = tuple(service.name for service in services)
            self._ask(session, Stage.SERVICE_SELECTION, IntentType.SELECT_ITEM, options=options)
            return WorkflowResult(
                replies=(self.responses.service_results(services),),
                events=(
                    WorkflowEvent(
                        event_type="booking.service_options_presented",
                        data={"candidate_count": len(services)},
                    ),
                ),
            )
        draft.select_service(services[0])
        return await self._after_service_selected(
            context,
            initial_replies=(self.responses.service_detail(services[0]),),
            preferred_date=context.intent.entities.preferred_date,
        )

    async def _select_service(self, context: WorkflowContext) -> WorkflowResult:
        session = context.session
        if session.flow != Flow.BOOKING or session.stage != Stage.SERVICE_SELECTION:
            raise BookingStateError("service selection is not expected now")
        draft = self._require_draft(session)
        selection = context.intent.entities.selection
        if selection is None:
            raise BookingStateError("service selection requires a selection entity")
        service = self._select_service_candidate(draft.service_candidates, selection)
        draft.select_service(service)
        return await self._after_service_selected(
            context,
            initial_replies=(self.responses.service_detail(service),),
            preferred_date=None,
        )

    async def _after_service_selected(
        self,
        context: WorkflowContext,
        *,
        initial_replies: tuple[WorkflowReply, ...],
        preferred_date: date | None,
    ) -> WorkflowResult:
        session = context.session
        session.transition_to(self.transition_policy, Flow.BOOKING, Stage.PREFERRED_DATE)
        if preferred_date is not None:
            result = await self._apply_date(context, preferred_date)
            return WorkflowResult(
                replies=(*initial_replies, *result.replies),
                events=(
                    WorkflowEvent(event_type="booking.service_selected"),
                    *result.events,
                ),
            )
        self._ask(session, Stage.PREFERRED_DATE, IntentType.PROVIDE_DATE)
        return WorkflowResult(
            replies=(
                *initial_replies,
                self.responses.ask_for_missing_booking_field("preferred_date"),
            ),
            events=(WorkflowEvent(event_type="booking.service_selected"),),
        )

    async def _provide_date(self, context: WorkflowContext) -> WorkflowResult:
        preferred_date = context.intent.entities.preferred_date
        if preferred_date is None:
            raise BookingStateError("date intent requires preferred_date")
        return await self._apply_date(context, preferred_date)

    async def _apply_date(self, context: WorkflowContext, preferred_date: date) -> WorkflowResult:
        session = context.session
        draft = self._require_draft(session)
        if session.flow != Flow.BOOKING or session.stage != Stage.PREFERRED_DATE:
            raise BookingStateError("preferred date is not expected now")
        now = self.clock()
        if now.tzinfo is None:
            raise ValueError("booking workflow clock must be timezone-aware")
        if preferred_date < now.date():
            self._ask(session, Stage.PREFERRED_DATE, IntentType.PROVIDE_DATE)
            return WorkflowResult(
                replies=(
                    self.responses.clarification(
                        "Please choose today or a future date in YYYY-MM-DD format."
                    ),
                ),
                events=(WorkflowEvent(event_type="booking.past_date_rejected"),),
            )
        if draft.service is None:
            raise BookingStateError("booking service has not been selected")
        draft.set_preferred_date(preferred_date)
        slots = await self.tradeflow.get_available_slots(
            context.business_id,
            draft.service.service_id,
            appointment_date=preferred_date,
        )
        draft.set_available_slots(slots)
        if not slots:
            self._ask(session, Stage.PREFERRED_DATE, IntentType.PROVIDE_DATE)
            return WorkflowResult(
                replies=(self.responses.available_slots(()),),
                events=(WorkflowEvent(event_type="booking.slots_unavailable"),),
            )
        session.transition_to(self.transition_policy, Flow.BOOKING, Stage.TIME_SELECTION)
        self._ask(
            session,
            Stage.TIME_SELECTION,
            IntentType.SELECT_TIME,
            options=tuple(self._slot_label(slot) for slot in slots),
        )
        return WorkflowResult(
            replies=(self.responses.available_slots(slots),),
            events=(
                WorkflowEvent(
                    event_type="booking.slots_presented",
                    data={"slot_count": len(slots)},
                ),
            ),
        )

    async def _select_time(self, context: WorkflowContext) -> WorkflowResult:
        session = context.session
        draft = self._require_draft(session)
        if session.flow != Flow.BOOKING or session.stage != Stage.TIME_SELECTION:
            raise BookingStateError("time selection is not expected now")
        slot = self._select_slot(
            draft.available_slots,
            context.intent.entities.selection,
            context.intent.entities.start_time,
        )
        draft.select_slot(slot)
        return await self._after_slot_selected(context)

    async def _after_slot_selected(self, context: WorkflowContext) -> WorkflowResult:
        session = context.session
        draft = self._require_draft(session)
        if draft.service is None or draft.selected_slot is None:
            raise BookingStateError("service and slot must be selected")
        if draft.selected_slot.staff_id is not None:
            return await self._move_to_customer_details(context)
        staff = await self.tradeflow.get_qualified_staff(
            context.business_id,
            draft.service.service_id,
            appointment_date=draft.selected_slot.appointment_date,
            start_time=draft.selected_slot.start_time,
        )
        options = tuple(
            BookingStaffOption(item.staff_id, item.name)
            for item in staff[: self.config.maximum_staff_options]
        )
        draft.set_staff_options(options)
        if len(options) == 1:
            draft.select_staff(options[0].staff_id, options[0].name)
            return await self._move_to_customer_details(context)
        if len(options) > 1:
            session.transition_to(self.transition_policy, Flow.BOOKING, Stage.STAFF_SELECTION)
            self._ask(
                session,
                Stage.STAFF_SELECTION,
                IntentType.SELECT_STAFF,
                options=tuple(option.name for option in options),
                allow_skip=True,
            )
            return WorkflowResult(
                replies=(
                    self.responses.staff_options(
                        tuple(StaffOption(option.staff_id, option.name) for option in options),
                        allow_no_preference=True,
                    ),
                ),
                events=(
                    WorkflowEvent(
                        event_type="booking.staff_options_presented",
                        data={"staff_count": len(options)},
                    ),
                ),
            )
        return await self._move_to_customer_details(context)

    async def _select_staff(self, context: WorkflowContext) -> WorkflowResult:
        session = context.session
        draft = self._require_draft(session)
        if session.flow != Flow.BOOKING or session.stage != Stage.STAFF_SELECTION:
            raise BookingStateError("staff selection is not expected now")
        if context.intent.entities.extras.get("skip_staff") is True:
            draft.clear_staff()
        else:
            selection = context.intent.entities.selection
            if selection is None:
                raise BookingStateError("staff selection requires a choice or skip")
            option = self._select_staff_candidate(draft.staff_options, selection)
            draft.select_staff(option.staff_id, option.name)
        return await self._move_to_customer_details(context)

    async def _move_to_customer_details(self, context: WorkflowContext) -> WorkflowResult:
        session = context.session
        session.transition_to(self.transition_policy, Flow.BOOKING, Stage.CUSTOMER_DETAILS)
        entities = context.intent.entities
        if entities.customer_name and entities.contact_number:
            return await self._provide_customer(context)
        self._ask(session, Stage.CUSTOMER_DETAILS, IntentType.PROVIDE_CUSTOMER_DETAILS)
        return WorkflowResult(
            replies=(self.responses.ask_for_missing_booking_field("customer_name"),),
            events=(WorkflowEvent(event_type="booking.slot_selected"),),
        )

    async def _provide_customer(self, context: WorkflowContext) -> WorkflowResult:
        session = context.session
        draft = self._require_draft(session)
        if session.flow != Flow.BOOKING or session.stage != Stage.CUSTOMER_DETAILS:
            raise BookingStateError("customer details are not expected now")
        name = context.intent.entities.customer_name
        contact = context.intent.entities.contact_number
        if name is None or contact is None:
            raise BookingStateError("customer details intent requires name and contact")
        draft.set_customer(name, contact)
        return await self._prepare_review(context, fresh_confirmation=False)

    async def _prepare_review(
        self,
        context: WorkflowContext,
        *,
        fresh_confirmation: bool,
    ) -> WorkflowResult:
        session = context.session
        draft = self._require_draft(session)
        validation = await self._validate_live(context, draft)
        if isinstance(validation, WorkflowResult):
            return validation
        service_changed = draft.service != validation[0]
        draft.service = validation[0]
        draft.selected_slot = validation[1]
        draft.apply_final_validation(
            slot_confirmed=True,
            validation_reference=f"slot:{context.message_id}",
        )
        if session.stage != Stage.BOOKING_REVIEW:
            session.transition_to(self.transition_policy, Flow.BOOKING, Stage.BOOKING_REVIEW)
        self._ask(session, Stage.BOOKING_REVIEW, IntentType.CONFIRM)
        reply = (
            self.responses.booking_price_changed_review(draft)
            if service_changed and fresh_confirmation
            else self.responses.booking_review(draft)
        )
        return WorkflowResult(
            replies=(reply,),
            events=(
                WorkflowEvent(
                    event_type="booking.review_presented",
                    data={"service_changed": service_changed},
                ),
            ),
        )

    async def _confirm(self, context: WorkflowContext) -> WorkflowResult:
        session = context.session
        draft = self._require_draft(session)
        if draft.submitted:
            return WorkflowResult(
                replies=(self.responses.booking_submitted(self._stored_submission(draft)),),
                events=(WorkflowEvent(event_type="booking.submission_replayed"),),
            )
        if session.flow != Flow.BOOKING or session.stage not in {
            Stage.BOOKING_REVIEW,
            Stage.CUSTOMER_CONFIRMATION,
            Stage.SUBMITTED,
        }:
            raise BookingStateError("booking confirmation is not expected now")
        old_service = draft.service
        validation = await self._validate_live(context, draft)
        if isinstance(validation, WorkflowResult):
            return validation
        current_service, current_slot = validation
        price_changed = old_service != current_service
        draft.service = current_service
        draft.selected_slot = current_slot
        draft.apply_final_validation(
            slot_confirmed=True,
            validation_reference=f"slot:{context.message_id}",
        )
        if price_changed:
            if session.stage != Stage.BOOKING_REVIEW:
                session.transition_to(self.transition_policy, Flow.BOOKING, Stage.BOOKING_REVIEW)
            self._ask(session, Stage.BOOKING_REVIEW, IntentType.CONFIRM)
            return WorkflowResult(
                replies=(self.responses.booking_price_changed_review(draft),),
                events=(WorkflowEvent(event_type="booking.service_changed"),),
            )
        session.transition_to(self.transition_policy, Flow.BOOKING, Stage.SUBMITTING)
        result = await self.tradeflow.create_booking_request(
            context.business_id,
            self._submission_request(draft),
            idempotency_key=draft.idempotency_key,
        )
        draft.mark_submitted(result.request_id, result.status)
        session.transition_to(self.transition_policy, Flow.BOOKING, Stage.SUBMITTED)
        session.clear_pending_question()
        return WorkflowResult(
            replies=(self.responses.booking_submitted(result),),
            events=(
                WorkflowEvent(
                    event_type="booking.submitted",
                    data={"created": result.created},
                ),
            ),
        )

    async def _validate_live(
        self,
        context: WorkflowContext,
        draft: BookingDraft,
    ) -> tuple[ServiceSelection, AppointmentSlot] | WorkflowResult:
        if draft.service is None or draft.preferred_date is None or draft.selected_slot is None:
            raise BookingStateError("booking draft is incomplete for validation")
        current_service = await self.tradeflow.get_service(
            context.business_id,
            draft.service.service_id,
        )
        if current_service is None:
            draft.clear_service()
            self._transition(session=context.session, stage=Stage.SERVICE_SELECTION)
            self._ask(context.session, Stage.SERVICE_SELECTION, IntentType.SELECT_ITEM, options=())
            return WorkflowResult(
                replies=(self.responses.no_catalogue_match(item_name="service"),),
                events=(WorkflowEvent(event_type="booking.service_removed"),),
            )
        selected_slot_id = draft.selected_slot.slot_id
        slots = await self.tradeflow.get_available_slots(
            context.business_id,
            current_service.service_id,
            appointment_date=draft.preferred_date,
        )
        draft.set_available_slots(slots)
        current_slot = next(
            (slot for slot in slots if slot.slot_id == selected_slot_id),
            None,
        )
        if current_slot is None:
            draft.clear_slot()
            if slots:
                self._transition(session=context.session, stage=Stage.TIME_SELECTION)
                self._ask(
                    context.session,
                    Stage.TIME_SELECTION,
                    IntentType.SELECT_TIME,
                    options=tuple(self._slot_label(slot) for slot in slots),
                )
                return WorkflowResult(
                    replies=(self.responses.slot_no_longer_available(slots),),
                    events=(WorkflowEvent(event_type="booking.slot_changed"),),
                )
            draft.clear_date()
            self._transition(session=context.session, stage=Stage.PREFERRED_DATE)
            self._ask(context.session, Stage.PREFERRED_DATE, IntentType.PROVIDE_DATE)
            return WorkflowResult(
                replies=(self.responses.available_slots(()),),
                events=(WorkflowEvent(event_type="booking.date_no_longer_available"),),
            )
        if draft.preferred_staff_id is not None:
            staff = await self.tradeflow.get_qualified_staff(
                context.business_id,
                current_service.service_id,
                appointment_date=current_slot.appointment_date,
                start_time=current_slot.start_time,
            )
            chosen = next(
                (item for item in staff if item.staff_id == draft.preferred_staff_id),
                None,
            )
            if chosen is None:
                draft.clear_staff()
                options = tuple(
                    BookingStaffOption(item.staff_id, item.name)
                    for item in staff[: self.config.maximum_staff_options]
                )
                draft.set_staff_options(options)
                if len(options) > 1:
                    self._transition(session=context.session, stage=Stage.STAFF_SELECTION)
                    self._ask(
                        context.session,
                        Stage.STAFF_SELECTION,
                        IntentType.SELECT_STAFF,
                        options=tuple(item.name for item in options),
                        allow_skip=True,
                    )
                    return WorkflowResult(
                        replies=(
                            self.responses.staff_no_longer_available(
                                tuple(StaffOption(item.staff_id, item.name) for item in options)
                            ),
                        ),
                        events=(WorkflowEvent(event_type="booking.staff_changed"),),
                    )
            else:
                current_slot = AppointmentSlot(
                    slot_id=current_slot.slot_id,
                    service_id=current_slot.service_id,
                    appointment_date=current_slot.appointment_date,
                    start_time=current_slot.start_time,
                    end_time=current_slot.end_time,
                    staff_id=chosen.staff_id,
                    staff_name=chosen.name,
                )
        return current_service, current_slot

    async def _correct(self, context: WorkflowContext) -> WorkflowResult:
        session = context.session
        draft = self._require_draft(session)
        field = str(context.intent.entities.extras.get("field") or "").strip()
        if not field:
            return WorkflowResult(
                replies=(self.responses.correction_prompt(Flow.BOOKING, "booking"),),
                events=(WorkflowEvent(event_type="booking.correction_field_missing"),),
            )
        if field == "service":
            draft.clear_service()
            self._transition(session, Stage.SERVICE_SELECTION)
            self._ask(session, Stage.SERVICE_SELECTION, IntentType.SELECT_ITEM, options=())
        elif field == "preferred_date":
            draft.clear_date()
            self._transition(session, Stage.PREFERRED_DATE)
            self._ask(session, Stage.PREFERRED_DATE, IntentType.PROVIDE_DATE)
        elif field in {"time", "selected_slot"}:
            draft.clear_slot()
            if not draft.available_slots:
                self._transition(session, Stage.PREFERRED_DATE)
                self._ask(session, Stage.PREFERRED_DATE, IntentType.PROVIDE_DATE)
                field = "preferred_date"
            else:
                self._transition(session, Stage.TIME_SELECTION)
                self._ask(
                    session,
                    Stage.TIME_SELECTION,
                    IntentType.SELECT_TIME,
                    options=tuple(self._slot_label(slot) for slot in draft.available_slots),
                )
                field = "selected_slot"
        elif field == "staff":
            draft.clear_staff()
            self._transition(session, Stage.STAFF_SELECTION)
            self._ask(
                session,
                Stage.STAFF_SELECTION,
                IntentType.SELECT_STAFF,
                options=tuple(item.name for item in draft.staff_options),
                allow_skip=True,
            )
        elif field == "customer_details":
            draft.clear_customer()
            self._transition(session, Stage.CUSTOMER_DETAILS)
            self._ask(session, Stage.CUSTOMER_DETAILS, IntentType.PROVIDE_CUSTOMER_DETAILS)
        else:
            return WorkflowResult(
                replies=(self.responses.correction_prompt(Flow.BOOKING, "booking"),),
                events=(WorkflowEvent(event_type="booking.correction_field_unknown"),),
            )
        return WorkflowResult(
            replies=(self.responses.correction_prompt(Flow.BOOKING, field),),
            events=(WorkflowEvent(event_type="booking.correction_started", data={"field": field}),),
        )

    async def _cancel(self, context: WorkflowContext) -> WorkflowResult:
        context.session.cancel_active_flow(self.transition_policy)
        return WorkflowResult(
            replies=(self.responses.cancelled(),),
            events=(WorkflowEvent(event_type="booking.cancelled"),),
        )

    def _ask(
        self,
        session: Session,
        stage: Stage,
        expected: IntentType,
        *,
        options: tuple[str, ...] | None = None,
        allow_skip: bool = False,
    ) -> None:
        field_map = {
            Stage.SERVICE_SELECTION: "service",
            Stage.PREFERRED_DATE: "preferred_date",
            Stage.TIME_SELECTION: "selected_slot",
            Stage.STAFF_SELECTION: "staff",
            Stage.CUSTOMER_DETAILS: "customer_name",
        }
        prompt_reply = self.responses.ask_for_missing_booking_field(field_map.get(stage, "booking"))
        prompt = prompt_reply.text or "Please continue your booking request."
        metadata: dict[str, object] = {}
        if options is not None:
            metadata["options"] = options
        if allow_skip:
            metadata["allow_skip"] = True
        session.set_pending_question(
            PendingQuestion(
                prompt=prompt,
                expected_intents=frozenset({expected}),
                metadata=metadata,
            )
        )

    def _transition(self, session: Session, stage: Stage) -> None:
        if session.flow == Flow.BOOKING and session.stage == stage:
            return
        session.transition_to(self.transition_policy, Flow.BOOKING, stage)

    @staticmethod
    def _require_draft(session: Session) -> BookingDraft:
        if session.booking_draft is None:
            raise BookingStateError("booking session has no draft")
        return session.booking_draft

    @staticmethod
    def _service_query(raw: str) -> str:
        tokens = [
            token
            for token in _TOKEN_PATTERN.findall(raw.casefold())
            if token not in _GENERIC_BOOKING_TERMS and not token.isdigit()
        ]
        return " ".join(tokens)

    @staticmethod
    def _select_service_candidate(
        candidates: Sequence[ServiceSelection],
        selection: str | int,
    ) -> ServiceSelection:
        if isinstance(selection, int) or str(selection).strip().rstrip(".").isdigit():
            index = int(str(selection).strip().rstrip(".")) - 1
            if 0 <= index < len(candidates):
                return candidates[index]
            raise BookingStateError("service selection number is outside the list")
        cleaned = str(selection).strip().casefold()
        matches = [item for item in candidates if cleaned in item.name.casefold()]
        if len(matches) == 1:
            return matches[0]
        raise BookingStateError("service selection is ambiguous or invalid")

    @staticmethod
    def _select_slot(
        slots: Sequence[AppointmentSlot],
        selection: str | int | None,
        start_time: time | None,
    ) -> AppointmentSlot:
        if selection is not None and (
            isinstance(selection, int) or str(selection).strip().rstrip(".").isdigit()
        ):
            index = int(str(selection).strip().rstrip(".")) - 1
            if 0 <= index < len(slots):
                return slots[index]
            raise BookingStateError("time selection number is outside the list")
        if start_time is not None:
            matches = [slot for slot in slots if slot.start_time == start_time]
            if len(matches) == 1:
                return matches[0]
        raise BookingStateError("time selection is ambiguous or invalid")

    @staticmethod
    def _select_staff_candidate(
        candidates: Sequence[BookingStaffOption],
        selection: str | int,
    ) -> BookingStaffOption:
        if isinstance(selection, int) or str(selection).strip().rstrip(".").isdigit():
            index = int(str(selection).strip().rstrip(".")) - 1
            if 0 <= index < len(candidates):
                return candidates[index]
            raise BookingStateError("staff selection number is outside the list")
        cleaned = str(selection).strip().casefold()
        matches = [item for item in candidates if cleaned in item.name.casefold()]
        if len(matches) == 1:
            return matches[0]
        raise BookingStateError("staff selection is ambiguous or invalid")

    @staticmethod
    def _slot_label(slot: AppointmentSlot) -> str:
        return f"{slot.start_time.strftime('%H:%M')}-{slot.end_time.strftime('%H:%M')}"

    @staticmethod
    def _submission_request(draft: BookingDraft) -> BookingSubmissionRequest:
        if (
            draft.service is None
            or draft.selected_slot is None
            or draft.customer_name is None
            or draft.contact_number is None
        ):
            raise BookingStateError("booking draft is incomplete")
        return BookingSubmissionRequest(
            service_id=draft.service.service_id,
            slot_id=draft.selected_slot.slot_id,
            appointment_date=draft.selected_slot.appointment_date,
            start_time=draft.selected_slot.start_time,
            customer_name=draft.customer_name,
            contact_number=draft.contact_number,
            staff_id=draft.preferred_staff_id,
        )

    @staticmethod
    def _stored_submission(draft: BookingDraft) -> SubmissionResult:
        if draft.submitted_request_id is None or draft.submitted_status is None:
            raise BookingStateError("submitted booking has no stored result")
        return SubmissionResult(
            request_id=draft.submitted_request_id,
            status=draft.submitted_status,
            created=False,
        )

    def _dependency_failure(self, error: Exception, *, retryable: bool) -> WorkflowResult:
        return WorkflowResult(
            replies=(
                self.responses.dependency_failure(
                    retryable=retryable,
                    action_name="the booking request",
                ),
            ),
            events=(
                WorkflowEvent(
                    event_type="booking.dependency_failed",
                    data={
                        "retryable": retryable,
                        "error_type": type(error).__name__,
                    },
                ),
            ),
        )


def build_booking_routes(
    workflow: WorkflowHandler,
) -> Mapping[IntentType, WorkflowHandler]:
    """Return WorkflowRouter registrations owned by the booking workflow."""

    return {
        IntentType.START_BOOKING: workflow,
        IntentType.SELECT_ITEM: workflow,
        IntentType.PROVIDE_DATE: workflow,
        IntentType.SELECT_TIME: workflow,
        IntentType.SELECT_STAFF: workflow,
        IntentType.PROVIDE_CUSTOMER_DETAILS: workflow,
        IntentType.CONFIRM: workflow,
        IntentType.CORRECT: workflow,
        IntentType.CANCEL: workflow,
    }
