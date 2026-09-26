"""Product-order collection, review, correction, and submission workflow."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from ntheemba.application.workflow_router import (
    WorkflowContext,
    WorkflowEvent,
    WorkflowHandler,
    WorkflowReply,
    WorkflowResult,
)
from ntheemba.domain.enums import (
    Flow,
    FulfilmentMethod,
    IntentType,
    ProductResolutionStatus,
    Stage,
)
from ntheemba.domain.intents import EntitySet, Intent, PendingQuestion
from ntheemba.domain.order_draft import OrderDraft, PriceSnapshot
from ntheemba.domain.product_resolution import ResolvedProduct
from ntheemba.domain.session import Session
from ntheemba.domain.transitions import TransitionPolicy
from ntheemba.ports.tradeflow import (
    OrderSubmissionRequest,
    ProductAvailability,
    SubmissionResult,
    TradeFlowPort,
)
from ntheemba.services.response_builder import ResponseBuilder
from ntheemba.workflows.catalogue import CatalogueWorkflow

_SUPPORTED_INTENTS = frozenset(
    {
        IntentType.START_ORDER,
        IntentType.CATALOGUE_SEARCH,
        IntentType.SELECT_ITEM,
        IntentType.PROVIDE_QUANTITY,
        IntentType.PROVIDE_FULFILMENT_METHOD,
        IntentType.PROVIDE_DELIVERY_DETAILS,
        IntentType.PROVIDE_CUSTOMER_DETAILS,
        IntentType.CONFIRM,
        IntentType.CORRECT,
        IntentType.CANCEL,
    }
)
_GENERIC_ORDER_TERMS = frozenset(
    {
        "a",
        "an",
        "buy",
        "can",
        "get",
        "i",
        "it",
        "like",
        "need",
        "order",
        "please",
        "purchase",
        "some",
        "the",
        "this",
        "to",
        "want",
        "would",
    }
)
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


class UnsupportedOrderIntentError(ValueError):
    """Raised when the order workflow receives an intent it does not own."""


class OrderStateError(ValueError):
    """Raised when order state is missing or internally inconsistent."""


@dataclass(frozen=True, slots=True)
class OrderWorkflowConfig:
    """Order workflow behavior."""

    require_fresh_confirmation_on_price_change: bool = True


class OrderWorkflow:
    """Collect and submit one customer order request."""

    def __init__(
        self,
        *,
        catalogue: CatalogueWorkflow,
        tradeflow: TradeFlowPort,
        responses: ResponseBuilder,
        transition_policy: TransitionPolicy | None = None,
        config: OrderWorkflowConfig | None = None,
    ) -> None:
        self.catalogue = catalogue
        self.tradeflow = tradeflow
        self.responses = responses
        self.transition_policy = transition_policy or TransitionPolicy()
        self.config = config or OrderWorkflowConfig()

    async def handle(self, context: WorkflowContext) -> WorkflowResult:
        """Handle one approved order intent."""

        intent_type = context.intent.type
        if intent_type not in _SUPPORTED_INTENTS:
            raise UnsupportedOrderIntentError(
                f"order workflow does not handle {intent_type.value!r}"
            )

        if intent_type == IntentType.START_ORDER:
            return await self._start(context)
        if intent_type in {IntentType.CATALOGUE_SEARCH, IntentType.SELECT_ITEM}:
            return await self.catalogue.handle(context)
        if intent_type == IntentType.PROVIDE_QUANTITY:
            return await self._provide_quantity(context)
        if intent_type == IntentType.PROVIDE_FULFILMENT_METHOD:
            return await self._provide_fulfilment(context)
        if intent_type == IntentType.PROVIDE_DELIVERY_DETAILS:
            return await self._provide_delivery_details(context)
        if intent_type == IntentType.PROVIDE_CUSTOMER_DETAILS:
            return await self._provide_customer_details(context)
        if intent_type == IntentType.CONFIRM:
            return await self._confirm(context)
        if intent_type == IntentType.CORRECT:
            return self._correct(context)
        return self._cancel(context)

    async def _start(self, context: WorkflowContext) -> WorkflowResult:
        session = context.session
        selected = self._selected_product(session)

        if session.flow == Flow.CATALOGUE and session.stage == Stage.PRODUCT_SELECTED:
            if selected is None:
                raise OrderStateError("catalogue selection is missing resolved product data")
            session.order_draft = (
                OrderDraft(
                    product=selected,
                    idempotency_key=context.mutation_idempotency_key,
                )
                if context.mutation_idempotency_key
                else OrderDraft(product=selected)
            )
            session.transition_to(
                self.transition_policy,
                Flow.ORDER,
                Stage.QUANTITY,
            )
            if context.intent.entities.quantity is not None:
                return await self._apply_quantity(
                    context,
                    context.intent.entities.quantity,
                    initial_replies=(),
                    source="catalogue_selected_start",
                )
            self._ask(session, Stage.QUANTITY, IntentType.PROVIDE_QUANTITY)
            return WorkflowResult(
                replies=(self.responses.ask_for_missing_order_field("quantity"),),
                events=(
                    WorkflowEvent(
                        event_type="order.started_from_catalogue",
                        data={"product_preselected": True},
                    ),
                ),
            )

        if session.flow == Flow.IDLE and session.stage in {
            Stage.CANCELLED,
            Stage.RESOLVED,
        }:
            session.transition_to(self.transition_policy, Flow.IDLE, Stage.START)

        if session.flow != Flow.IDLE or session.stage != Stage.START:
            raise OrderStateError("a new order can only start from idle or a selected product")

        session.order_draft = (
            OrderDraft(idempotency_key=context.mutation_idempotency_key)
            if context.mutation_idempotency_key
            else OrderDraft()
        )
        session.booking_draft = None
        session.product_resolution = None
        session.transition_to(
            self.transition_policy,
            Flow.ORDER,
            Stage.CATALOGUE_SEARCH,
        )

        if not self._has_product_clue(context.intent.entities):
            self._ask(session, Stage.CATALOGUE_SEARCH, IntentType.CATALOGUE_SEARCH)
            return WorkflowResult(
                replies=(self.responses.ask_for_missing_order_field("product"),),
                events=(
                    WorkflowEvent(
                        event_type="order.started",
                        data={"product_query_supplied": False},
                    ),
                ),
            )

        catalogue_result = await self.catalogue.handle(
            WorkflowContext(
                session=session,
                intent=Intent(
                    type=IntentType.CATALOGUE_SEARCH,
                    role=context.intent.role,
                    confidence=context.intent.confidence,
                    entities=context.intent.entities,
                    reasoning_code="order_delegated_catalogue_search",
                ),
                business_id=context.business_id,
                customer_id=context.customer_id,
                request_id=context.request_id,
                message_id=context.message_id,
            )
        )

        if self._current_stage(session) != Stage.PRODUCT_SELECTED:
            return WorkflowResult(
                replies=catalogue_result.replies,
                events=(
                    WorkflowEvent(
                        event_type="order.started",
                        data={"product_query_supplied": True},
                    ),
                    *catalogue_result.events,
                ),
            )

        self._ensure_draft_product(session)
        if context.intent.entities.quantity is None:
            return WorkflowResult(
                replies=catalogue_result.replies,
                events=(
                    WorkflowEvent(
                        event_type="order.started",
                        data={"product_query_supplied": True},
                    ),
                    *catalogue_result.events,
                ),
            )

        replies = self._without_quantity_prompt(catalogue_result.replies)
        quantity_result = await self._apply_quantity(
            context,
            context.intent.entities.quantity,
            initial_replies=replies,
            source="combined_start",
        )
        return WorkflowResult(
            replies=quantity_result.replies,
            events=(
                WorkflowEvent(
                    event_type="order.started",
                    data={"product_query_supplied": True},
                ),
                *catalogue_result.events,
                *quantity_result.events,
            ),
        )

    async def _provide_quantity(self, context: WorkflowContext) -> WorkflowResult:
        quantity = context.intent.entities.quantity
        if quantity is None:
            self._ask(context.session, Stage.QUANTITY, IntentType.PROVIDE_QUANTITY)
            return WorkflowResult(
                replies=(self.responses.ask_for_missing_order_field("quantity"),),
                events=(
                    WorkflowEvent(
                        event_type="order.quantity_missing",
                        data={"source": "customer_answer"},
                    ),
                ),
            )
        return await self._apply_quantity(
            context,
            quantity,
            initial_replies=(),
            source="customer_answer",
        )

    async def _apply_quantity(
        self,
        context: WorkflowContext,
        quantity: int,
        *,
        initial_replies: tuple[WorkflowReply, ...],
        source: str,
    ) -> WorkflowResult:
        session = context.session
        draft = self._ensure_draft_product(session)
        if session.flow != Flow.ORDER or session.stage not in {
            Stage.PRODUCT_SELECTED,
            Stage.QUANTITY,
        }:
            raise OrderStateError("quantity is not expected in the current order stage")
        if session.stage == Stage.PRODUCT_SELECTED:
            session.transition_to(self.transition_policy, Flow.ORDER, Stage.QUANTITY)

        draft.set_quantity(quantity)
        availability = await self._check_availability(context, draft)
        if isinstance(availability, WorkflowResult):
            return WorkflowResult(
                replies=(*initial_replies, *availability.replies),
                events=(*availability.events,),
            )
        if not availability.available:
            unavailable = self._unavailable_result(
                session,
                draft,
                availability,
                event_type="order.quantity_unavailable",
                requested_quantity=quantity,
            )
            return WorkflowResult(
                replies=(*initial_replies, *unavailable.replies),
                events=unavailable.events,
            )

        draft.apply_final_validation(
            price=PriceSnapshot(availability.selling_price, availability.currency),
            availability_confirmed=True,
            validation_reference=f"availability:{context.message_id}",
        )
        session.transition_to(
            self.transition_policy,
            Flow.ORDER,
            Stage.FULFILMENT_METHOD,
        )
        self._ask(
            session,
            Stage.FULFILMENT_METHOD,
            IntentType.PROVIDE_FULFILMENT_METHOD,
        )

        if context.intent.entities.fulfilment_method is not None:
            fulfilment_context = WorkflowContext(
                session=session,
                intent=Intent(
                    type=IntentType.PROVIDE_FULFILMENT_METHOD,
                    role=context.intent.role,
                    confidence=context.intent.confidence,
                    entities=EntitySet(
                        fulfilment_method=context.intent.entities.fulfilment_method,
                        delivery_details=context.intent.entities.delivery_details,
                        customer_name=context.intent.entities.customer_name,
                        contact_number=context.intent.entities.contact_number,
                        raw_text=context.intent.entities.raw_text,
                    ),
                    reasoning_code="order_combined_fulfilment",
                ),
                business_id=context.business_id,
                customer_id=context.customer_id,
                request_id=context.request_id,
                message_id=context.message_id,
            )
            result = await self._provide_fulfilment(fulfilment_context)
            return WorkflowResult(
                replies=(*initial_replies, *result.replies),
                events=(
                    WorkflowEvent(
                        event_type="order.quantity_recorded",
                        data={"quantity": quantity, "source": source},
                    ),
                    *result.events,
                ),
            )

        return WorkflowResult(
            replies=(
                *initial_replies,
                self.responses.ask_for_missing_order_field("fulfilment_method"),
            ),
            events=(
                WorkflowEvent(
                    event_type="order.quantity_recorded",
                    data={"quantity": quantity, "source": source},
                ),
            ),
        )

    async def _provide_fulfilment(self, context: WorkflowContext) -> WorkflowResult:
        session = context.session
        draft = self._require_draft(session)
        method = context.intent.entities.fulfilment_method
        if method is None:
            raise OrderStateError("fulfilment intent requires a fulfilment method")
        if session.flow != Flow.ORDER or session.stage != Stage.FULFILMENT_METHOD:
            raise OrderStateError("fulfilment method is not expected now")

        draft.set_fulfilment_method(method)
        if method == FulfilmentMethod.DELIVERY:
            session.transition_to(
                self.transition_policy,
                Flow.ORDER,
                Stage.DELIVERY_DETAILS,
            )
            if context.intent.entities.delivery_details:
                delivery_context = WorkflowContext(
                    session=session,
                    intent=Intent(
                        type=IntentType.PROVIDE_DELIVERY_DETAILS,
                        role=context.intent.role,
                        confidence=context.intent.confidence,
                        entities=context.intent.entities,
                        reasoning_code="order_combined_delivery_details",
                    ),
                    business_id=context.business_id,
                    customer_id=context.customer_id,
                    request_id=context.request_id,
                    message_id=context.message_id,
                )
                return await self._provide_delivery_details(delivery_context)
            self._ask(
                session,
                Stage.DELIVERY_DETAILS,
                IntentType.PROVIDE_DELIVERY_DETAILS,
            )
            return WorkflowResult(
                replies=(self.responses.ask_for_missing_order_field("delivery_details"),),
                events=(
                    WorkflowEvent(
                        event_type="order.fulfilment_recorded",
                        data={"method": method.value},
                    ),
                ),
            )

        session.transition_to(
            self.transition_policy,
            Flow.ORDER,
            Stage.CUSTOMER_DETAILS,
        )
        if context.intent.entities.customer_name and context.intent.entities.contact_number:
            customer_context = WorkflowContext(
                session=session,
                intent=Intent(
                    type=IntentType.PROVIDE_CUSTOMER_DETAILS,
                    role=context.intent.role,
                    confidence=context.intent.confidence,
                    entities=context.intent.entities,
                    reasoning_code="order_combined_customer_details",
                ),
                business_id=context.business_id,
                customer_id=context.customer_id,
                request_id=context.request_id,
                message_id=context.message_id,
            )
            return await self._provide_customer_details(customer_context)
        self._ask(
            session,
            Stage.CUSTOMER_DETAILS,
            IntentType.PROVIDE_CUSTOMER_DETAILS,
        )
        return WorkflowResult(
            replies=(self.responses.ask_for_missing_order_field("customer_name"),),
            events=(
                WorkflowEvent(
                    event_type="order.fulfilment_recorded",
                    data={"method": method.value},
                ),
            ),
        )

    async def _provide_delivery_details(self, context: WorkflowContext) -> WorkflowResult:
        session = context.session
        draft = self._require_draft(session)
        details = context.intent.entities.delivery_details
        if not details:
            raise OrderStateError("delivery-details intent requires delivery details")
        if session.flow != Flow.ORDER or session.stage != Stage.DELIVERY_DETAILS:
            raise OrderStateError("delivery details are not expected now")

        draft.set_delivery_details(details)
        session.transition_to(
            self.transition_policy,
            Flow.ORDER,
            Stage.CUSTOMER_DETAILS,
        )
        self._ask(
            session,
            Stage.CUSTOMER_DETAILS,
            IntentType.PROVIDE_CUSTOMER_DETAILS,
        )
        return WorkflowResult(
            replies=(self.responses.ask_for_missing_order_field("customer_name"),),
            events=(
                WorkflowEvent(
                    event_type="order.delivery_details_recorded",
                    data={"length": len(details.strip())},
                ),
            ),
        )

    async def _provide_customer_details(self, context: WorkflowContext) -> WorkflowResult:
        session = context.session
        draft = self._require_draft(session)
        name = context.intent.entities.customer_name
        contact = context.intent.entities.contact_number
        if not name or not contact:
            raise OrderStateError("customer-details intent requires name and contact")
        if session.flow != Flow.ORDER or session.stage != Stage.CUSTOMER_DETAILS:
            raise OrderStateError("customer details are not expected now")

        draft.set_customer(name, contact)
        result = await self._prepare_review(context)
        return WorkflowResult(
            replies=result.replies,
            events=(
                WorkflowEvent(
                    event_type="order.customer_details_recorded",
                    data={"contact_length": len(contact)},
                ),
                *result.events,
            ),
        )

    async def _prepare_review(self, context: WorkflowContext) -> WorkflowResult:
        session = context.session
        draft = self._require_draft(session)
        if not draft.ready_for_review:
            missing = draft.missing_fields()[0]
            return self._move_to_missing_field(session, missing)

        availability = await self._check_availability(context, draft)
        if isinstance(availability, WorkflowResult):
            return availability
        if not availability.available:
            return self._unavailable_result(
                session,
                draft,
                availability,
                event_type="order.review_stock_rejected",
            )

        draft.apply_final_validation(
            price=PriceSnapshot(availability.selling_price, availability.currency),
            availability_confirmed=True,
            validation_reference=f"review:{context.message_id}",
        )
        session.transition_to(
            self.transition_policy,
            Flow.ORDER,
            Stage.ORDER_REVIEW,
        )
        self._ask(session, Stage.ORDER_REVIEW, IntentType.CONFIRM)
        return WorkflowResult(
            replies=(self.responses.order_review(draft),),
            events=(
                WorkflowEvent(
                    event_type="order.review_presented",
                    data={
                        "quantity": draft.quantity,
                        "fulfilment_method": draft.fulfilment_method.value
                        if draft.fulfilment_method
                        else "",
                    },
                ),
            ),
        )

    async def _confirm(self, context: WorkflowContext) -> WorkflowResult:
        session = context.session
        draft = self._require_draft(session)
        if session.flow != Flow.ORDER:
            raise OrderStateError("order confirmation requires the order flow")

        if session.stage == Stage.SUBMITTED:
            result = self._stored_submission(draft)
            return WorkflowResult(
                replies=(self.responses.order_submitted(result),),
                events=(
                    WorkflowEvent(
                        event_type="order.submission_replayed",
                        data={"created": False},
                    ),
                ),
            )

        if session.stage not in {Stage.ORDER_REVIEW, Stage.CUSTOMER_CONFIRMATION}:
            raise OrderStateError("order is not ready for confirmation")
        if not draft.ready_for_review:
            raise OrderStateError("order draft is incomplete")

        availability = await self._check_availability(context, draft)
        if isinstance(availability, WorkflowResult):
            return availability
        if not availability.available:
            return self._unavailable_result(
                session,
                draft,
                availability,
                event_type="order.confirmation_stock_rejected",
            )

        previous_price = draft.price_snapshot
        price_changed = previous_price is not None and (
            previous_price.amount != availability.selling_price
            or previous_price.currency != availability.currency
        )
        draft.apply_final_validation(
            price=PriceSnapshot(availability.selling_price, availability.currency),
            availability_confirmed=True,
            validation_reference=f"confirm:{context.message_id}",
        )
        if price_changed and self.config.require_fresh_confirmation_on_price_change:
            self._ask(session, Stage.ORDER_REVIEW, IntentType.CONFIRM)
            return WorkflowResult(
                replies=(
                    self.responses.price_changed_order_review(
                        draft,
                        previous_amount=previous_price.amount if previous_price else None,
                        previous_currency=previous_price.currency if previous_price else None,
                    ),
                ),
                events=(
                    WorkflowEvent(
                        event_type="order.price_changed",
                        data={
                            "requires_confirmation": True,
                        },
                    ),
                ),
            )

        session.transition_to(
            self.transition_policy,
            Flow.ORDER,
            Stage.SUBMITTING,
        )
        try:
            result = await self.tradeflow.create_order_request(
                context.business_id,
                self._submission_request(draft),
                idempotency_key=draft.idempotency_key,
            )
        except (ConnectionError, TimeoutError) as error:
            session.transition_to(
                self.transition_policy,
                Flow.ORDER,
                Stage.ORDER_REVIEW,
            )
            self._ask(session, Stage.ORDER_REVIEW, IntentType.CONFIRM)
            return self._dependency_failure(error, retryable=True, operation="order submission")
        except LookupError as error:
            session.transition_to(
                self.transition_policy,
                Flow.ORDER,
                Stage.ORDER_REVIEW,
            )
            self._ask(session, Stage.ORDER_REVIEW, IntentType.CONFIRM)
            return self._dependency_failure(error, retryable=False, operation="order submission")

        draft.mark_submitted(result.request_id, result.status)
        session.transition_to(
            self.transition_policy,
            Flow.ORDER,
            Stage.SUBMITTED,
        )
        session.clear_pending_question()
        return WorkflowResult(
            replies=(self.responses.order_submitted(result),),
            events=(
                WorkflowEvent(
                    event_type="order.submitted",
                    data={
                        "created": result.created,
                        "status": result.status,
                    },
                ),
            ),
        )

    def _correct(self, context: WorkflowContext) -> WorkflowResult:
        session = context.session
        draft = self._require_draft(session)
        if session.flow != Flow.ORDER or session.stage in {
            Stage.SUBMITTING,
            Stage.SUBMITTED,
        }:
            raise OrderStateError("this order can no longer be corrected")

        field = str(context.intent.entities.extras.get("field", "")).strip()
        if not field:
            return WorkflowResult(
                replies=(self.responses.correction_prompt(Flow.ORDER, ""),),
                events=(WorkflowEvent(event_type="order.correction_field_missing"),),
            )

        if field == "product":
            draft.clear_product()
            session.product_resolution = None
            self._transition_for_correction(session, Stage.CATALOGUE_SEARCH)
            self._ask(session, Stage.CATALOGUE_SEARCH, IntentType.CATALOGUE_SEARCH)
        elif field == "quantity":
            draft.clear_quantity()
            self._transition_for_correction(session, Stage.QUANTITY)
            self._ask(session, Stage.QUANTITY, IntentType.PROVIDE_QUANTITY)
        elif field == "fulfilment_method":
            draft.clear_fulfilment()
            self._transition_for_correction(session, Stage.FULFILMENT_METHOD)
            self._ask(
                session,
                Stage.FULFILMENT_METHOD,
                IntentType.PROVIDE_FULFILMENT_METHOD,
            )
        elif field == "delivery_details":
            if draft.fulfilment_method != FulfilmentMethod.DELIVERY:
                return WorkflowResult(
                    replies=(
                        self.responses.clarification(
                            "This order is set for collection, so it has no delivery details."
                        ),
                    ),
                    events=(
                        WorkflowEvent(
                            event_type="order.correction_not_applicable",
                            data={"field": field},
                        ),
                    ),
                )
            draft.clear_delivery_details()
            self._transition_for_correction(session, Stage.DELIVERY_DETAILS)
            self._ask(
                session,
                Stage.DELIVERY_DETAILS,
                IntentType.PROVIDE_DELIVERY_DETAILS,
            )
        elif field == "customer_details":
            draft.clear_customer()
            self._transition_for_correction(session, Stage.CUSTOMER_DETAILS)
            self._ask(
                session,
                Stage.CUSTOMER_DETAILS,
                IntentType.PROVIDE_CUSTOMER_DETAILS,
            )
        else:
            return WorkflowResult(
                replies=(self.responses.correction_prompt(Flow.ORDER, ""),),
                events=(
                    WorkflowEvent(
                        event_type="order.correction_field_unknown",
                        data={"field_length": len(field)},
                    ),
                ),
            )

        return WorkflowResult(
            replies=(self.responses.correction_prompt(Flow.ORDER, field),),
            events=(
                WorkflowEvent(
                    event_type="order.correction_started",
                    data={"field": field, "stage": session.stage.value},
                ),
            ),
        )

    def _cancel(self, context: WorkflowContext) -> WorkflowResult:
        session = context.session
        if session.flow != Flow.ORDER:
            raise OrderStateError("order cancellation requires the order flow")
        previous_stage = session.stage
        session.cancel_active_flow(self.transition_policy)
        return WorkflowResult(
            replies=(self.responses.cancelled(),),
            events=(
                WorkflowEvent(
                    event_type="order.cancelled",
                    data={"previous_stage": previous_stage.value},
                ),
            ),
        )

    async def _check_availability(
        self,
        context: WorkflowContext,
        draft: OrderDraft,
    ) -> ProductAvailability | WorkflowResult:
        if draft.product is None or draft.quantity is None:
            raise OrderStateError("availability check requires product and quantity")
        try:
            return await self.tradeflow.check_product_availability(
                context.business_id,
                draft.product.business_product_id,
                quantity=draft.quantity,
                shop_id=draft.product.shop_id,
            )
        except (ConnectionError, TimeoutError) as error:
            return self._dependency_failure(
                error,
                retryable=True,
                operation="stock and price validation",
            )
        except LookupError as error:
            return self._dependency_failure(
                error,
                retryable=False,
                operation="stock and price validation",
            )

    def _unavailable_result(
        self,
        session: Session,
        draft: OrderDraft,
        availability: ProductAvailability,
        *,
        event_type: str,
        requested_quantity: int | None = None,
    ) -> WorkflowResult:
        if availability.public_visible:
            draft.clear_quantity()
            self._transition_for_correction(session, Stage.QUANTITY)
            self._ask(session, Stage.QUANTITY, IntentType.PROVIDE_QUANTITY)
        else:
            draft.clear_product()
            session.product_resolution = None
            self._transition_for_correction(session, Stage.CATALOGUE_SEARCH)
            self._ask(session, Stage.CATALOGUE_SEARCH, IntentType.CATALOGUE_SEARCH)
        return WorkflowResult(
            replies=(self.responses.quantity_unavailable(availability),),
            events=(
                WorkflowEvent(
                    event_type=event_type,
                    data={
                        "requested_quantity": requested_quantity
                        if requested_quantity is not None
                        else availability.requested_quantity,
                        "available_quantity": availability.available_quantity,
                        "public_visible": availability.public_visible,
                    },
                ),
            ),
        )

    def _move_to_missing_field(self, session: Session, field: str) -> WorkflowResult:
        stage_and_intent = {
            "product": (Stage.CATALOGUE_SEARCH, IntentType.CATALOGUE_SEARCH),
            "quantity": (Stage.QUANTITY, IntentType.PROVIDE_QUANTITY),
            "fulfilment_method": (
                Stage.FULFILMENT_METHOD,
                IntentType.PROVIDE_FULFILMENT_METHOD,
            ),
            "delivery_details": (
                Stage.DELIVERY_DETAILS,
                IntentType.PROVIDE_DELIVERY_DETAILS,
            ),
            "customer_name": (
                Stage.CUSTOMER_DETAILS,
                IntentType.PROVIDE_CUSTOMER_DETAILS,
            ),
            "contact_number": (
                Stage.CUSTOMER_DETAILS,
                IntentType.PROVIDE_CUSTOMER_DETAILS,
            ),
        }
        try:
            stage, expected = stage_and_intent[field]
        except KeyError as error:
            raise OrderStateError(f"unsupported missing order field {field!r}") from error
        self._transition_for_correction(session, stage)
        self._ask(session, stage, expected)
        return WorkflowResult(
            replies=(self.responses.ask_for_missing_order_field(field),),
            events=(
                WorkflowEvent(
                    event_type="order.missing_field_requested",
                    data={"field": field},
                ),
            ),
        )

    def _ask(self, session: Session, stage: Stage, expected: IntentType) -> None:
        prompt = (
            "Reply CONFIRM to submit, CORRECT to change something, or CANCEL."
            if stage == Stage.ORDER_REVIEW
            else self.responses.ask_for_missing_order_field(self._field_for_stage(stage)).text
        )
        if not prompt:
            raise OrderStateError("missing-field response has no text")
        session.set_pending_question(
            PendingQuestion(
                prompt=prompt,
                expected_intents=frozenset({expected}),
            )
        )

    @staticmethod
    def _field_for_stage(stage: Stage) -> str:
        mapping = {
            Stage.CATALOGUE_SEARCH: "product",
            Stage.PRODUCT_SELECTED: "quantity",
            Stage.QUANTITY: "quantity",
            Stage.FULFILMENT_METHOD: "fulfilment_method",
            Stage.DELIVERY_DETAILS: "delivery_details",
            Stage.CUSTOMER_DETAILS: "customer_name",
            Stage.ORDER_REVIEW: "confirmation",
        }
        return mapping.get(stage, "order")

    def _transition_for_correction(self, session: Session, stage: Stage) -> None:
        if session.flow == Flow.ORDER and session.stage == stage:
            return
        session.transition_to(self.transition_policy, Flow.ORDER, stage)

    @staticmethod
    def _require_draft(session: Session) -> OrderDraft:
        if session.order_draft is None:
            raise OrderStateError("order session has no draft")
        return session.order_draft

    def _ensure_draft_product(self, session: Session) -> OrderDraft:
        draft = session.order_draft or OrderDraft()
        selected = self._selected_product(session)
        if selected is None:
            raise OrderStateError("order product has not been resolved")
        if draft.product != selected:
            draft.select_product(selected)
        session.order_draft = draft
        return draft

    @staticmethod
    def _current_stage(session: Session) -> Stage:
        """Return current stage without retaining earlier type narrowing."""

        return session.stage

    @staticmethod
    def _selected_product(session: Session) -> ResolvedProduct | None:
        resolution = session.product_resolution
        if (
            resolution is None
            or resolution.status != ProductResolutionStatus.RESOLVED
            or resolution.selected is None
        ):
            return None
        return resolution.selected

    @staticmethod
    def _has_product_clue(entities: EntitySet) -> bool:
        if any(
            (
                entities.brand,
                entities.product_family,
                entities.variant,
                entities.barcode,
                entities.relative_size,
            )
        ):
            return True
        query = (entities.query or entities.raw_text).casefold()
        tokens = set(_TOKEN_PATTERN.findall(query)) - _GENERIC_ORDER_TERMS
        return bool(tokens)

    @staticmethod
    def _without_quantity_prompt(
        replies: tuple[WorkflowReply, ...],
    ) -> tuple[WorkflowReply, ...]:
        return tuple(
            reply
            for reply in replies
            if not (
                reply.metadata.get("response_type") == "order_missing_field"
                and reply.metadata.get("field") == "quantity"
            )
        )

    @staticmethod
    def _submission_request(draft: OrderDraft) -> OrderSubmissionRequest:
        if (
            draft.product is None
            or draft.quantity is None
            or draft.fulfilment_method is None
            or draft.customer_name is None
            or draft.contact_number is None
        ):
            raise OrderStateError("order draft is incomplete")
        return OrderSubmissionRequest(
            business_product_id=draft.product.business_product_id,
            quantity=draft.quantity,
            fulfilment_method=draft.fulfilment_method,
            customer_name=draft.customer_name,
            contact_number=draft.contact_number,
            delivery_details=draft.delivery_details or "",
            shop_id=draft.product.shop_id,
        )

    @staticmethod
    def _stored_submission(draft: OrderDraft) -> SubmissionResult:
        if draft.submitted_request_id is None or draft.submitted_status is None:
            raise OrderStateError("submitted order has no stored submission result")
        return SubmissionResult(
            request_id=draft.submitted_request_id,
            status=draft.submitted_status,
            created=False,
        )

    def _dependency_failure(
        self,
        error: Exception,
        *,
        retryable: bool,
        operation: str,
    ) -> WorkflowResult:
        return WorkflowResult(
            replies=(
                self.responses.dependency_failure(
                    retryable=retryable,
                    action_name=operation,
                ),
            ),
            events=(
                WorkflowEvent(
                    event_type="order.dependency_failed",
                    data={
                        "operation": operation,
                        "retryable": retryable,
                        "error_type": type(error).__name__,
                    },
                ),
            ),
        )


def build_order_routes(
    workflow: WorkflowHandler,
) -> Mapping[IntentType, WorkflowHandler]:
    """Return WorkflowRouter registrations owned by the order workflow."""

    return {
        IntentType.START_ORDER: workflow,
        IntentType.PROVIDE_QUANTITY: workflow,
        IntentType.PROVIDE_FULFILMENT_METHOD: workflow,
        IntentType.PROVIDE_DELIVERY_DETAILS: workflow,
        IntentType.PROVIDE_CUSTOMER_DETAILS: workflow,
        IntentType.CONFIRM: workflow,
        IntentType.CORRECT: workflow,
        IntentType.CANCEL: workflow,
    }
