"""Product catalogue search, clarification, selection, and detail workflow."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import monotonic

from ntheemba.application.workflow_router import (
    WorkflowContext,
    WorkflowEvent,
    WorkflowHandler,
    WorkflowReply,
    WorkflowResult,
)
from ntheemba.domain.enums import (
    Flow,
    IntentType,
    ProductResolutionOutcome,
    ProductResolutionStatus,
    SessionStatus,
    Stage,
)
from ntheemba.domain.intents import PendingQuestion
from ntheemba.domain.order_draft import OrderDraft
from ntheemba.domain.product_resolution import (
    ProductCandidate,
    ProductResolution,
    ResolvedProduct,
)
from ntheemba.domain.session import ClarificationLimitReached, Session
from ntheemba.domain.transitions import TransitionPolicy
from ntheemba.ports.tradeflow import BusinessProduct, TradeFlowPort
from ntheemba.services.product_resolver import (
    ProductNoneOfTheseError,
    ProductResolutionDependencyError,
    ProductResolutionError,
    ProductResolver,
    ProductSelectionError,
)
from ntheemba.services.response_builder import ResponseBuilder

_SUPPORTED_INTENTS = frozenset(
    {
        IntentType.CATALOGUE_SEARCH,
        IntentType.SELECT_ITEM,
    }
)
_CATALOGUE_STAGES = frozenset(
    {
        Stage.CATALOGUE_SEARCH,
        Stage.ITEM_SELECTION,
        Stage.PRODUCT_CLARIFICATION,
        Stage.PRODUCT_SELECTED,
    }
)


class UnsupportedCatalogueIntentError(ValueError):
    """Raised when the catalogue workflow receives an intent it does not own."""


class CatalogueStateError(ValueError):
    """Raised when selection is attempted without saved candidates."""


@dataclass(frozen=True, slots=True)
class CatalogueWorkflowConfig:
    """Limits for catalogue clarification and escalation."""

    maximum_selection_attempts: int = 3
    pending_candidate_ttl: timedelta = timedelta(minutes=15)

    def __post_init__(self) -> None:
        if self.maximum_selection_attempts <= 0:
            raise ValueError("maximum_selection_attempts must be greater than zero")
        if self.pending_candidate_ttl <= timedelta(0):
            raise ValueError("pending_candidate_ttl must be greater than zero")


class CatalogueWorkflow:
    """Resolve products and keep all candidate state inside the session."""

    def __init__(
        self,
        *,
        resolver: ProductResolver,
        tradeflow: TradeFlowPort,
        responses: ResponseBuilder,
        transition_policy: TransitionPolicy | None = None,
        config: CatalogueWorkflowConfig | None = None,
    ) -> None:
        self.resolver = resolver
        self.tradeflow = tradeflow
        self.responses = responses
        self.transition_policy = transition_policy or TransitionPolicy()
        self.config = config or CatalogueWorkflowConfig()

    async def handle(self, context: WorkflowContext) -> WorkflowResult:
        """Handle a product search or a selection from saved candidates."""

        if context.session.status == SessionStatus.EXPIRED:
            return self._session_expired(context)

        if context.intent.type not in _SUPPORTED_INTENTS:
            raise UnsupportedCatalogueIntentError(
                f"catalogue workflow does not handle {context.intent.type.value!r}"
            )

        if context.intent.type == IntentType.CATALOGUE_SEARCH:
            return await self._search(context)
        return await self._select(context)

    async def _search(self, context: WorkflowContext) -> WorkflowResult:
        session = context.session
        owner_flow = self._prepare_search_state(session)
        session.product_resolution = None
        session.clear_clarification()

        try:
            started_at = monotonic()
            resolution = await self.resolver.resolve_from_entities(
                context.business_id,
                context.intent.entities,
            )
        except ProductResolutionDependencyError as error:
            return self._dependency_failure(
                context,
                error,
                owner_flow=owner_flow,
                elapsed_ms=_elapsed_ms(started_at),
            )
        except ProductResolutionError:
            return WorkflowResult(
                replies=(
                    self.responses.clarification(
                        "Which product would you like me to find? "
                        "Include a name, brand, size, or barcode."
                    ),
                ),
                events=(
                    WorkflowEvent(
                        event_type="catalogue.query_invalid",
                        data={"flow": owner_flow.value},
                    ),
                ),
            )
        except (ConnectionError, TimeoutError) as error:
            return self._dependency_failure(
                context,
                error,
                owner_flow=owner_flow,
                retryable=True,
                operation="product search",
                outcome=ProductResolutionOutcome.NCPC_TIMEOUT,
                dependency="ncpc",
                elapsed_ms=_elapsed_ms(started_at),
            )
        except LookupError as error:
            return self._dependency_failure(
                context,
                error,
                owner_flow=owner_flow,
                retryable=False,
                operation="product search",
                outcome=ProductResolutionOutcome.MALFORMED_RESPONSE,
                dependency="ncpc",
                elapsed_ms=_elapsed_ms(started_at),
            )

        resolution = self._scope_pending_resolution(context, resolution)
        if resolution.status == ProductResolutionStatus.RESOLVED:
            try:
                started_at = monotonic()
                product = await self._live_product(context.business_id, resolution)
            except ProductResolutionDependencyError as error:
                return self._dependency_failure(
                    context,
                    error,
                    owner_flow=owner_flow,
                    elapsed_ms=_elapsed_ms(started_at),
                )
            except (ConnectionError, TimeoutError) as error:
                return self._dependency_failure(
                    context,
                    error,
                    owner_flow=owner_flow,
                    retryable=True,
                    operation="product details",
                    outcome=ProductResolutionOutcome.TRADEFLOW_TIMEOUT,
                    dependency="tradeflow",
                    elapsed_ms=_elapsed_ms(started_at),
                )
            except LookupError as error:
                return self._dependency_failure(
                    context,
                    error,
                    owner_flow=owner_flow,
                    retryable=False,
                    operation="product details",
                    outcome=ProductResolutionOutcome.MALFORMED_RESPONSE,
                    dependency="tradeflow",
                    elapsed_ms=_elapsed_ms(started_at),
                )
            if product is None:
                return self._product_disappeared(session, resolution, owner_flow)
            return self._complete_selection(
                session,
                resolution,
                product,
                owner_flow=owner_flow,
                source="search",
            )

        session.product_resolution = resolution
        if resolution.status == ProductResolutionStatus.NO_MATCH:
            session.clear_pending_question()
            outcome = resolution.outcome or ProductResolutionOutcome.NCPC_NO_MATCH
            return WorkflowResult(
                replies=(self.responses.product_resolution_failure(outcome),),
                events=(
                    WorkflowEvent(
                        event_type="catalogue.no_match",
                        data={
                            **self._base_event_data(context, owner_flow),
                            "outcome": outcome.value,
                            "flow": owner_flow.value,
                            "candidate_count": 0,
                            "safe_to_retry": True,
                        },
                    ),
                ),
            )

        if resolution.status == ProductResolutionStatus.NEEDS_CLARIFICATION:
            self._transition(session, owner_flow, Stage.PRODUCT_CLARIFICATION)
            self._set_selection_question(session, resolution)
            return WorkflowResult(
                replies=(self.responses.product_clarification(resolution),),
                events=(
                    WorkflowEvent(
                        event_type="catalogue.clarification_requested",
                        data={
                            **self._base_event_data(context, owner_flow),
                            "outcome": ProductResolutionOutcome.SHOP_MATCHES.value,
                            "flow": owner_flow.value,
                            "candidate_count": len(resolution.candidates),
                            "resolution_status": resolution.status.value,
                        },
                    ),
                ),
            )

        if resolution.status in {
            ProductResolutionStatus.ONE_MATCH,
            ProductResolutionStatus.SUGGEST_CONFIRMATION,
        }:
            self._transition(session, owner_flow, Stage.ITEM_SELECTION)
            self._set_selection_question(session, resolution)
            candidate = resolution.candidates[0]
            reason = (
                "I found one possible product."
                if resolution.status == ProductResolutionStatus.ONE_MATCH
                else "This appears to be the closest match."
            )
            return WorkflowResult(
                replies=(self.responses.product_suggestion(candidate, reason=reason),),
                events=(
                    WorkflowEvent(
                        event_type="catalogue.confirmation_requested",
                        data={
                            **self._base_event_data(context, owner_flow),
                            "outcome": ProductResolutionOutcome.SHOP_MATCHES.value,
                            "flow": owner_flow.value,
                            "candidate_count": len(resolution.candidates),
                            "resolution_status": resolution.status.value,
                        },
                    ),
                ),
            )

        raise CatalogueStateError(
            f"unsupported product resolution status {resolution.status.value!r}"
        )

    async def _select(self, context: WorkflowContext) -> WorkflowResult:
        session = context.session
        owner_flow = self._owner_flow(session)
        resolution = session.product_resolution
        if resolution is None or resolution.status not in {
            ProductResolutionStatus.ONE_MATCH,
            ProductResolutionStatus.SUGGEST_CONFIRMATION,
            ProductResolutionStatus.NEEDS_CLARIFICATION,
        }:
            raise CatalogueStateError("product selection requires a saved selectable resolution")
        stale_result = self._stale_or_cross_scope_selection(context, resolution, owner_flow)
        if stale_result is not None:
            return stale_result

        selection = context.intent.entities.selection
        if selection is None:
            selection = context.intent.entities.raw_text.strip()

        try:
            selected_resolution = self.resolver.resolve_selection(
                resolution,
                selection,
            )
        except ProductNoneOfTheseError:
            return self._none_of_these(session, resolution, owner_flow)
        except ProductSelectionError:
            return self._invalid_selection(session, resolution, owner_flow)

        try:
            started_at = monotonic()
            product = await self._live_product(
                context.business_id,
                selected_resolution,
            )
        except ProductResolutionDependencyError as error:
            return self._dependency_failure(
                context,
                error,
                owner_flow=owner_flow,
                elapsed_ms=_elapsed_ms(started_at),
            )
        except (ConnectionError, TimeoutError) as error:
            return self._dependency_failure(
                context,
                error,
                owner_flow=owner_flow,
                retryable=True,
                operation="product details",
                outcome=ProductResolutionOutcome.TRADEFLOW_TIMEOUT,
                dependency="tradeflow",
                elapsed_ms=_elapsed_ms(started_at),
            )
        except LookupError as error:
            return self._dependency_failure(
                context,
                error,
                owner_flow=owner_flow,
                retryable=False,
                operation="product details",
                outcome=ProductResolutionOutcome.MALFORMED_RESPONSE,
                dependency="tradeflow",
                elapsed_ms=_elapsed_ms(started_at),
            )

        if product is None:
            return self._product_disappeared(
                session,
                selected_resolution,
                owner_flow,
            )
        return self._complete_selection(
            session,
            selected_resolution,
            product,
            owner_flow=owner_flow,
            source="customer_selection",
        )

    def _prepare_search_state(self, session: Session) -> Flow:
        if session.flow == Flow.IDLE and session.stage in {
            Stage.CANCELLED,
            Stage.RESOLVED,
        }:
            session.transition_to(
                self.transition_policy,
                Flow.IDLE,
                Stage.START,
            )

        if session.flow == Flow.IDLE:
            session.transition_to(
                self.transition_policy,
                Flow.CATALOGUE,
                Stage.CATALOGUE_SEARCH,
            )
            return Flow.CATALOGUE

        owner_flow = self._owner_flow(session)
        if session.stage != Stage.CATALOGUE_SEARCH:
            self._transition(session, owner_flow, Stage.CATALOGUE_SEARCH)
        return owner_flow

    @staticmethod
    def _owner_flow(session: Session) -> Flow:
        if session.flow not in {Flow.CATALOGUE, Flow.ORDER}:
            raise CatalogueStateError("catalogue workflow requires catalogue or order ownership")
        if session.stage not in _CATALOGUE_STAGES:
            raise CatalogueStateError(f"stage {session.stage.value!r} is not a catalogue stage")
        return session.flow

    def _transition(self, session: Session, flow: Flow, stage: Stage) -> None:
        if session.flow == flow and session.stage == stage:
            return
        session.transition_to(self.transition_policy, flow, stage)

    def _set_selection_question(
        self,
        session: Session,
        resolution: ProductResolution,
    ) -> None:
        options = resolution.clarification_options or tuple(
            self._candidate_label(candidate) for candidate in resolution.candidates
        )
        allow_confirmation = resolution.status in {
            ProductResolutionStatus.ONE_MATCH,
            ProductResolutionStatus.SUGGEST_CONFIRMATION,
        }
        prompt = (
            "Is this the product you mean? Reply YES or tell me the correct size."
            if allow_confirmation
            else "Which product would you like? Reply with its number, name, or size."
        )
        session.set_pending_question(
            PendingQuestion(
                prompt=prompt,
                expected_intents=frozenset({IntentType.SELECT_ITEM}),
                metadata={
                    "options": options,
                    "allow_confirmation": allow_confirmation,
                },
            )
        )

    def _invalid_selection(
        self,
        session: Session,
        resolution: ProductResolution,
        owner_flow: Flow,
    ) -> WorkflowResult:
        pending = session.pending_question or PendingQuestion(
            prompt="Which product would you like?",
            expected_intents=frozenset({IntentType.SELECT_ITEM}),
        )
        try:
            session.request_clarification(
                pending,
                maximum_attempts=self.config.maximum_selection_attempts,
            )
        except ClarificationLimitReached:
            session.request_handover(
                self.transition_policy,
                preserve_workflow=True,
            )
            return WorkflowResult(
                replies=(self.responses.handover_requested(),),
                events=(
                    WorkflowEvent(
                        event_type="catalogue.selection_escalated",
                        data={
                            "flow": owner_flow.value,
                            "attempts": session.clarification_count,
                            "confirmed_context_available": _confirmed_context_available(
                                session
                            ),
                        },
                    ),
                ),
            )

        retry_reply: WorkflowReply
        if resolution.status == ProductResolutionStatus.NEEDS_CLARIFICATION:
            retry_reply = self.responses.product_clarification(resolution)
        else:
            retry_reply = self.responses.product_suggestion(
                resolution.candidates[0],
                reason="I could not match that choice.",
            )
        return WorkflowResult(
            replies=(retry_reply,),
            events=(
                WorkflowEvent(
                    event_type="catalogue.selection_invalid",
                    data={
                        "flow": owner_flow.value,
                        "attempt": session.clarification_count,
                        "resolution_status": resolution.status.value,
                    },
                ),
            ),
        )

    async def _live_product(
        self,
        business_id: str,
        resolution: ProductResolution,
    ) -> BusinessProduct | None:
        selected = resolution.selected
        if selected is None:
            raise CatalogueStateError("resolved product is missing selected data")
        if selected.business_id != business_id:
            raise CatalogueStateError("resolved product belongs to another business")
        try:
            product = await self.tradeflow.get_business_product(
                business_id,
                selected.business_product_id,
            )
        except TimeoutError as error:
            raise ProductResolutionDependencyError(
                outcome=ProductResolutionOutcome.TRADEFLOW_TIMEOUT,
                dependency="tradeflow",
                operation="get_business_product",
                retryable=True,
            ) from error
        except PermissionError as error:
            raise ProductResolutionDependencyError(
                outcome=ProductResolutionOutcome.AUTH_FAILURE,
                dependency="tradeflow",
                operation="get_business_product",
                retryable=False,
            ) from error
        except (TypeError, ValueError) as error:
            raise ProductResolutionDependencyError(
                outcome=ProductResolutionOutcome.MALFORMED_RESPONSE,
                dependency="tradeflow",
                operation="get_business_product",
                retryable=False,
            ) from error
        if product is None or not product.public_visible:
            return None
        return product

    def _product_disappeared(
        self,
        session: Session,
        resolution: ProductResolution,
        owner_flow: Flow,
    ) -> WorkflowResult:
        session.product_resolution = ProductResolution.no_match(
            resolution.query,
            outcome=ProductResolutionOutcome.SHOP_NO_MATCH,
        )
        if owner_flow == Flow.ORDER and session.order_draft is not None:
            session.order_draft.clear_product()
        session.clear_pending_question()
        self._transition(session, owner_flow, Stage.CATALOGUE_SEARCH)
        return WorkflowResult(
            replies=(
                self.responses.product_resolution_failure(
                    ProductResolutionOutcome.SHOP_NO_MATCH,
                ),
            ),
            events=(
                WorkflowEvent(
                    event_type="catalogue.product_no_longer_public",
                    data={"flow": owner_flow.value},
                ),
            ),
        )

    def _complete_selection(
        self,
        session: Session,
        resolution: ProductResolution,
        product: BusinessProduct,
        *,
        owner_flow: Flow,
        source: str,
    ) -> WorkflowResult:
        selected_only = self._selected_only_resolution(resolution)
        session.product_resolution = selected_only
        session.clear_clarification()
        self._transition(session, owner_flow, Stage.PRODUCT_SELECTED)
        replies = self.responses.product_detail(product)
        order_draft_initialized = False
        if owner_flow == Flow.ORDER:
            if resolution.selected is None:
                raise CatalogueStateError("resolved order product has no selected data")
            draft = session.order_draft or OrderDraft()
            draft.select_product(resolution.selected)
            session.order_draft = draft
            quantity_reply = self.responses.ask_for_missing_order_field("quantity")
            if quantity_reply.text is None:
                raise CatalogueStateError("quantity prompt has no text")
            session.set_pending_question(
                PendingQuestion(
                    prompt=quantity_reply.text,
                    expected_intents=frozenset({IntentType.PROVIDE_QUANTITY}),
                )
            )
            replies = (*replies, quantity_reply)
            order_draft_initialized = True
        return WorkflowResult(
            replies=replies,
            events=(
                WorkflowEvent(
                    event_type="catalogue.product_selected",
                    data={
                        "correlation_id": resolution.correlation_id,
                        "outcome": "PRODUCT_SELECTED",
                        "flow": owner_flow.value,
                        "source": source,
                        "available": product.available,
                        "has_public_image": bool(product.image_url),
                        "candidate_count": len(resolution.candidates),
                        "order_draft_initialized": order_draft_initialized,
                        "business_id": resolution.selected.business_id
                        if resolution.selected is not None
                        else "",
                        "tradeflow_item_id": product.business_product_id,
                        "ncpc_product_id": product.ncpc_product_id,
                        "ncpc_variant_id": product.ncpc_variant_id,
                    },
                ),
            ),
        )

    def _scope_pending_resolution(
        self,
        context: WorkflowContext,
        resolution: ProductResolution,
    ) -> ProductResolution:
        return resolution.scoped(
            business_id=context.business_id,
            customer_id=context.customer_id,
            conversation_id=context.session.conversation_id,
            expires_at=datetime.now(UTC) + self.config.pending_candidate_ttl,
            correlation_id=context.request_id,
        )

    def _stale_or_cross_scope_selection(
        self,
        context: WorkflowContext,
        resolution: ProductResolution,
        owner_flow: Flow,
    ) -> WorkflowResult | None:
        if (
            resolution.business_id != context.business_id
            or resolution.customer_id != context.customer_id
            or resolution.conversation_id != context.session.conversation_id
        ):
            context.session.product_resolution = None
            context.session.clear_pending_question()
            self._transition(context.session, owner_flow, Stage.CATALOGUE_SEARCH)
            return WorkflowResult(
                replies=(
                    self.responses.product_resolution_failure(
                        ProductResolutionOutcome.STALE_SELECTION,
                    ),
                ),
                events=(
                    WorkflowEvent(
                        event_type="catalogue.selection_scope_rejected",
                        data={
                            **self._base_event_data(context, owner_flow),
                            "outcome": ProductResolutionOutcome.STALE_SELECTION.value,
                            "safe_to_retry": True,
                        },
                    ),
                ),
            )
        if resolution.expires_at is not None and datetime.now(UTC) >= resolution.expires_at:
            context.session.product_resolution = None
            context.session.clear_pending_question()
            self._transition(context.session, owner_flow, Stage.CATALOGUE_SEARCH)
            return WorkflowResult(
                replies=(
                    self.responses.product_resolution_failure(
                        ProductResolutionOutcome.STALE_SELECTION,
                    ),
                ),
                events=(
                    WorkflowEvent(
                        event_type="catalogue.selection_expired",
                        data={
                            **self._base_event_data(context, owner_flow),
                            "outcome": ProductResolutionOutcome.STALE_SELECTION.value,
                            "safe_to_retry": True,
                        },
                    ),
                ),
            )
        return None

    def _none_of_these(
        self,
        session: Session,
        resolution: ProductResolution,
        owner_flow: Flow,
    ) -> WorkflowResult:
        session.product_resolution = resolution
        session.request_handover(
            self.transition_policy,
            preserve_workflow=True,
        )
        return WorkflowResult(
            replies=(self.responses.handover_requested(),),
            events=(
                WorkflowEvent(
                    event_type="catalogue.none_of_these_handover",
                    data={
                        "flow": owner_flow.value,
                        "candidate_count": len(resolution.candidates),
                        "confirmed_context_available": _confirmed_context_available(
                            session
                        ),
                    },
                ),
            ),
        )

    @staticmethod
    def _selected_only_resolution(resolution: ProductResolution) -> ProductResolution:
        if resolution.selected is None:
            raise CatalogueStateError("resolved product is missing selected data")
        selected = ResolvedProduct(
            business_id=resolution.selected.business_id,
            ncpc_product_id=resolution.selected.ncpc_product_id,
            ncpc_variant_id=resolution.selected.ncpc_variant_id,
            business_product_id=resolution.selected.business_product_id,
            name=resolution.selected.name,
            selling_price=resolution.selected.selling_price,
            currency=resolution.selected.currency,
            available=resolution.selected.available,
            size_value=resolution.selected.size_value,
            size_unit=resolution.selected.size_unit,
            barcode=resolution.selected.barcode,
            shop_id=resolution.selected.shop_id,
            identity_status=resolution.selected.identity_status,
            trusted_identity=resolution.selected.trusted_identity,
        )
        return ProductResolution.resolved(
            resolution.query,
            selected,
            confidence=resolution.confidence,
            candidates=(),
        )

    def _dependency_failure(
        self,
        context: WorkflowContext,
        error: Exception,
        *,
        owner_flow: Flow,
        elapsed_ms: int,
        retryable: bool | None = None,
        operation: str | None = None,
        outcome: ProductResolutionOutcome | None = None,
        dependency: str | None = None,
    ) -> WorkflowResult:
        if isinstance(error, ProductResolutionDependencyError):
            retryable = error.retryable
            operation = error.operation
            outcome = error.outcome
            dependency = error.dependency
        if retryable is None or operation is None or outcome is None or dependency is None:
            raise CatalogueStateError("dependency failures require complete classification")
        return WorkflowResult(
            replies=(
                self.responses.product_resolution_failure(outcome),
            ),
            events=(
                WorkflowEvent(
                    event_type="catalogue.dependency_failed",
                    data={
                        **self._base_event_data(context, owner_flow),
                        "outcome": outcome.value,
                        "dependency": dependency,
                        "operation": operation,
                        "retryable": retryable,
                        "safe_to_retry": retryable,
                        "elapsed_ms": elapsed_ms,
                        "error_type": type(error).__name__,
                    },
                ),
            ),
        )

    def _session_expired(self, context: WorkflowContext) -> WorkflowResult:
        return WorkflowResult(
            replies=(
                self.responses.product_resolution_failure(
                    ProductResolutionOutcome.SESSION_EXPIRED,
                ),
            ),
            events=(
                WorkflowEvent(
                    event_type="catalogue.session_expired",
                    data={
                        **self._base_event_data(context, Flow.CATALOGUE),
                        "outcome": ProductResolutionOutcome.SESSION_EXPIRED.value,
                        "safe_to_retry": True,
                    },
                ),
            ),
        )

    @staticmethod
    def _base_event_data(context: WorkflowContext, owner_flow: Flow) -> dict[str, object]:
        return {
            "correlation_id": context.request_id,
            "message_id": context.message_id,
            "business_id": context.business_id,
            "conversation_id": context.session.conversation_id,
            "flow": owner_flow.value,
        }

    @staticmethod
    def _candidate_label(candidate: ProductCandidate) -> str:
        if candidate.size_value is None or candidate.size_unit is None:
            return candidate.name
        size = f"{format(candidate.size_value.normalize(), 'f')}{candidate.size_unit}"
        if size.casefold().replace(" ", "") in candidate.name.casefold().replace(" ", ""):
            return candidate.name
        return f"{candidate.name} — {size}"


def build_catalogue_routes(
    workflow: WorkflowHandler,
) -> Mapping[IntentType, WorkflowHandler]:
    """Return WorkflowRouter registrations owned by this workflow."""

    return {
        IntentType.CATALOGUE_SEARCH: workflow,
        IntentType.SELECT_ITEM: workflow,
    }


def _elapsed_ms(started_at: float) -> int:
    return max(0, round((monotonic() - started_at) * 1000))


def _confirmed_context_available(session: Session) -> bool:
    if session.product_resolution is not None and session.product_resolution.selected is not None:
        return True
    if session.order_draft is not None and session.order_draft.product is not None:
        return True
    if session.booking_draft is not None and session.booking_draft.service is not None:
        return True
    return False
