"""Rule-first customer-language interpretation with a validated model fallback."""

from __future__ import annotations

import inspect
import re
from collections.abc import Awaitable, Mapping
from datetime import date, time
from typing import Any, Protocol

from ntheemba.domain.capabilities import Capability
from ntheemba.domain.enums import (
    Flow,
    FulfilmentMethod,
    IntentType,
    ItemType,
    MessageRole,
    RelativeSize,
    Stage,
)
from ntheemba.domain.intents import EntitySet, Intent, PendingQuestion
from ntheemba.domain.session import Session
from ntheemba.services.validation import (
    InterpretationValidationError,
    ModelOutputValidator,
    validate_intent,
)

_DATE_PATTERN = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
_TIME_PATTERN = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
_PHONE_PATTERN = re.compile(r"\+?\d[\d\s-]{6,20}\d")
_INTEGER_PATTERN = re.compile(r"\b(\d+)\b")
_BARCODE_PATTERN = re.compile(r"(?<!\d)(\d{8,14})(?!\d)")
_SIZE_PATTERN = re.compile(r"\b(\d+(?:\.\d+)?)\s*(mg|g|kg|ml|l)\b", re.IGNORECASE)
_CATALOGUE_QUERY_PREFIX = re.compile(
    r"^\s*(?:do\s+you\s+(?:have|sell|stock)|show\s+me|find|"
    r"i\s+(?:want|need|would\s+like)\s+(?:to\s+)?(?:order|buy|get|purchase)|"
    r"i\s+(?:want|need|would\s+like)|"
    r"(?:order|buy|purchase|get))\s+",
    re.IGNORECASE,
)
_CONTROL_ACTIONS = frozenset(
    {
        IntentType.CANCEL,
        IntentType.CLOSE_SESSION,
        IntentType.CLARIFY,
        IntentType.CONTINUE,
        IntentType.CORRECT,
        IntentType.RESUME_BOT,
    }
)
_ACTION_REQUIREMENTS: Mapping[IntentType, frozenset[Capability]] = {
    IntentType.BUSINESS_INFO: frozenset({Capability.BUSINESS_INFORMATION}),
    IntentType.BUSINESS_HOURS: frozenset({Capability.BUSINESS_HOURS}),
    IntentType.FAQ: frozenset({Capability.FAQ}),
    IntentType.HANDOVER: frozenset({Capability.HANDOVER}),
    IntentType.LOYALTY_STATUS: frozenset({Capability.LOYALTY_READ}),
    IntentType.CATALOGUE_SEARCH: frozenset({Capability.PRODUCT_CATALOGUE}),
    IntentType.SELECT_ITEM: frozenset({Capability.PRODUCT_CATALOGUE}),
    IntentType.START_ORDER: frozenset(
        {Capability.PRODUCT_CATALOGUE, Capability.PRODUCT_ORDER}
    ),
    IntentType.PROVIDE_QUANTITY: frozenset(
        {Capability.PRODUCT_CATALOGUE, Capability.PRODUCT_ORDER}
    ),
    IntentType.PROVIDE_FULFILMENT_METHOD: frozenset(
        {Capability.PRODUCT_CATALOGUE, Capability.PRODUCT_ORDER}
    ),
    IntentType.PROVIDE_DELIVERY_DETAILS: frozenset(
        {Capability.PRODUCT_CATALOGUE, Capability.PRODUCT_ORDER, Capability.DELIVERY}
    ),
    IntentType.START_BOOKING: frozenset(
        {Capability.SERVICE_CATALOGUE, Capability.APPOINTMENT_CREATE}
    ),
    IntentType.PROVIDE_DATE: frozenset(
        {Capability.SERVICE_CATALOGUE, Capability.APPOINTMENT_CREATE}
    ),
    IntentType.SELECT_TIME: frozenset(
        {Capability.SERVICE_CATALOGUE, Capability.APPOINTMENT_CREATE}
    ),
    IntentType.SELECT_STAFF: frozenset(
        {Capability.SERVICE_CATALOGUE, Capability.APPOINTMENT_CREATE}
    ),
    IntentType.PROVIDE_CUSTOMER_DETAILS: frozenset(
        {Capability.SERVICE_CATALOGUE, Capability.APPOINTMENT_CREATE}
    ),
    IntentType.CONFIRM: frozenset(),
}


class ModelIntentProvider(Protocol):
    """Technology-neutral source of one intent proposal."""

    def propose(
        self,
        text: str,
        context: Mapping[str, Any],
    ) -> Mapping[str, Any] | Awaitable[Mapping[str, Any]]:
        """Return an untrusted mapping that must be validated."""


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _catalogue_query(text: str) -> str:
    candidate = _CATALOGUE_QUERY_PREFIX.sub("", text, count=1).strip()
    candidate = candidate.rstrip(" ?.!,:;")
    return candidate or text.strip()


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def allowed_actions_for_capabilities(
    capabilities: frozenset[Capability],
) -> frozenset[IntentType]:
    """Return model-visible actions supported by a compiled runtime profile."""

    allowed = set(_CONTROL_ACTIONS)
    for action, required in _ACTION_REQUIREMENTS.items():
        if required.issubset(capabilities):
            allowed.add(action)
    if Capability.SERVICE_CATALOGUE in capabilities:
        allowed.update({IntentType.CATALOGUE_SEARCH, IntentType.SELECT_ITEM})
    return frozenset(allowed)


def build_model_context(
    session: Session,
    capabilities: frozenset[Capability] = frozenset(),
) -> Mapping[str, Any]:
    """Build a minimal, customer-safe context for an intent model."""

    pending: dict[str, Any] | None = None
    if session.pending_question is not None:
        pending = {
            "prompt": session.pending_question.prompt,
            "expected_intents": sorted(
                intent.value for intent in session.pending_question.expected_intents
            ),
            "metadata": dict(session.pending_question.metadata),
        }
    history = [{"role": turn.role, "text": turn.text[:500]} for turn in session.recent_history[-6:]]
    allowed_actions = allowed_actions_for_capabilities(capabilities)
    return {
        "flow": session.flow.value,
        "stage": session.stage.value,
        "mode": session.mode.value,
        "status": session.status.value,
        "pending_question": pending,
        "conversation_summary": session.conversation_summary[:1000],
        "recent_history": history,
        "enabled_capabilities": sorted(capability.value for capability in capabilities),
        "allowed_actions": sorted(action.value for action in allowed_actions),
    }


class HybridInterpreter:
    """Use deterministic rules first and a strictly validated model only as fallback."""

    def __init__(
        self,
        *,
        model: ModelIntentProvider | None = None,
        validator: ModelOutputValidator | None = None,
    ) -> None:
        self.model = model
        self.validator = validator or ModelOutputValidator()

    async def interpret(
        self,
        text: str,
        session: Session,
        *,
        capabilities: frozenset[Capability] = frozenset(),
    ) -> Intent:
        """Interpret one message according to global, contextual, and fallback rules."""

        cleaned = text.strip()
        if not cleaned:
            return self._clarify(text, "empty_message")
        normalized = _normalize(cleaned)
        entities = self._extract_entities(cleaned)

        global_intent = self._global_command(normalized, cleaned, entities)
        if global_intent is not None:
            return validate_intent(global_intent)

        pending_intent = self._pending_answer(cleaned, normalized, entities, session)
        if pending_intent is not None:
            return validate_intent(pending_intent)

        interruption = self._safe_interruption(normalized, cleaned, entities, session)
        if interruption is not None:
            return validate_intent(interruption)

        new_request = self._new_request(normalized, cleaned, entities, session)
        if new_request is not None:
            return validate_intent(new_request)

        if self.model is not None:
            try:
                proposal = self.model.propose(
                    cleaned,
                    build_model_context(session, capabilities),
                )
                if inspect.isawaitable(proposal):
                    proposal = await proposal
                return self.validator.validate(
                    proposal,
                    raw_text=cleaned,
                    allowed_actions=allowed_actions_for_capabilities(capabilities),
                )
            except InterpretationValidationError:
                return self._clarify(cleaned, "model_output_rejected")

        return self._clarify(cleaned, "no_rule_or_model_match")

    def _global_command(
        self,
        normalized: str,
        raw: str,
        entities: EntitySet,
    ) -> Intent | None:
        if _contains_any(
            normalized,
            (
                "talk to a person",
                "speak to a person",
                "human agent",
                "real person",
                "manager please",
                "i need a human",
                "complaint",
            ),
        ) or normalized in {"human", "agent", "manager", "person"}:
            return Intent(
                type=IntentType.HANDOVER,
                role=MessageRole.GLOBAL_COMMAND,
                confidence=1.0,
                entities=EntitySet(raw_text=raw, extras={"reason": normalized}),
                reasoning_code="global_handover_rule",
            )
        if normalized in {"cancel", "stop", "never mind", "nevermind", "cancel it"}:
            return Intent(
                type=IntentType.CANCEL,
                role=MessageRole.GLOBAL_COMMAND,
                confidence=1.0,
                entities=EntitySet(raw_text=raw),
                reasoning_code="global_cancel_rule",
            )
        if normalized in {"resume bot", "resume", "bot can continue", "continue bot"}:
            return Intent(
                type=IntentType.RESUME_BOT,
                role=MessageRole.SYSTEM_COMMAND,
                confidence=1.0,
                entities=EntitySet(raw_text=raw),
                reasoning_code="global_resume_rule",
            )
        if normalized in {"close conversation", "close chat", "end conversation"}:
            return Intent(
                type=IntentType.CLOSE_SESSION,
                role=MessageRole.SYSTEM_COMMAND,
                confidence=1.0,
                entities=EntitySet(raw_text=raw),
                reasoning_code="global_close_rule",
            )
        if normalized.startswith(("change ", "correct ", "edit ", "go back")):
            field = self._correction_field(normalized)
            return Intent(
                type=IntentType.CORRECT,
                role=MessageRole.GLOBAL_COMMAND,
                confidence=0.99,
                entities=EntitySet(
                    raw_text=raw,
                    extras={"field": field} if field else {},
                ),
                reasoning_code="global_correction_rule",
            )
        return None

    def _pending_answer(
        self,
        raw: str,
        normalized: str,
        entities: EntitySet,
        session: Session,
    ) -> Intent | None:
        question = session.pending_question
        if question is None:
            return self._stage_answer(raw, normalized, entities, session)
        if (
            IntentType.PROVIDE_QUANTITY in question.expected_intents
            and session.flow == Flow.ORDER
            and session.stage in {Stage.PRODUCT_SELECTED, Stage.QUANTITY}
            and normalized in {"order this", "buy this", "get this", "continue"}
        ):
            return Intent(
                type=IntentType.PROVIDE_QUANTITY,
                role=MessageRole.PENDING_ANSWER,
                confidence=0.96,
                entities=EntitySet(raw_text=raw),
                reasoning_code="pending_quantity_prompt_rule",
            )
        for expected in question.expected_intents:
            intent = self._answer_for_intent(expected, raw, normalized, entities, question)
            if intent is not None:
                return intent
        return None

    def _stage_answer(
        self,
        raw: str,
        normalized: str,
        entities: EntitySet,
        session: Session,
    ) -> Intent | None:
        stage_to_intent = {
            Stage.CATALOGUE_SEARCH: IntentType.CATALOGUE_SEARCH,
            Stage.PRODUCT_SELECTED: IntentType.PROVIDE_QUANTITY,
            Stage.QUANTITY: IntentType.PROVIDE_QUANTITY,
            Stage.FULFILMENT_METHOD: IntentType.PROVIDE_FULFILMENT_METHOD,
            Stage.DELIVERY_DETAILS: IntentType.PROVIDE_DELIVERY_DETAILS,
            Stage.PREFERRED_DATE: IntentType.PROVIDE_DATE,
            Stage.TIME_SELECTION: IntentType.SELECT_TIME,
            Stage.STAFF_SELECTION: IntentType.SELECT_STAFF,
            Stage.CUSTOMER_DETAILS: IntentType.PROVIDE_CUSTOMER_DETAILS,
        }
        expected = stage_to_intent.get(session.stage)
        if expected is not None:
            if (
                expected == IntentType.PROVIDE_QUANTITY
                and session.flow == Flow.ORDER
                and session.stage == Stage.PRODUCT_SELECTED
                and normalized in {"order this", "buy this", "get this", "continue"}
            ):
                return Intent(
                    type=expected,
                    role=MessageRole.PENDING_ANSWER,
                    confidence=0.96,
                    entities=EntitySet(raw_text=raw),
                    reasoning_code="pending_quantity_prompt_rule",
                )
            return self._answer_for_intent(expected, raw, normalized, entities, None)
        if session.stage in {
            Stage.ORDER_REVIEW,
            Stage.BOOKING_REVIEW,
            Stage.CUSTOMER_CONFIRMATION,
        }:
            if normalized in {"yes", "y", "confirm", "confirmed", "submit", "ok", "okay"}:
                return Intent(
                    type=IntentType.CONFIRM,
                    role=MessageRole.PENDING_ANSWER,
                    confidence=1.0,
                    entities=EntitySet(raw_text=raw),
                    reasoning_code="review_confirmation_rule",
                )
        return None

    def _answer_for_intent(
        self,
        expected: IntentType,
        raw: str,
        normalized: str,
        entities: EntitySet,
        question: PendingQuestion | None,
    ) -> Intent | None:
        if expected == IntentType.CATALOGUE_SEARCH:
            if not raw.strip() or self._looks_like_question(normalized):
                return None
            return Intent(
                type=expected,
                role=MessageRole.PENDING_ANSWER,
                confidence=0.90,
                entities=EntitySet(
                    query=raw.strip(),
                    relative_size=entities.relative_size,
                    barcode=entities.barcode,
                    raw_text=raw,
                ),
                reasoning_code="pending_catalogue_query_rule",
            )
        if expected == IntentType.SELECT_ITEM:
            selection = self._match_selection(raw, entities, question)
            if selection is None:
                return None
            return Intent(
                type=expected,
                role=MessageRole.PENDING_ANSWER,
                confidence=0.99,
                entities=EntitySet(selection=selection, raw_text=raw),
                reasoning_code="pending_selection_rule",
            )
        if expected == IntentType.PROVIDE_QUANTITY:
            quantity = entities.quantity or self._word_quantity(normalized)
            if quantity is None:
                return None
            return Intent(
                type=expected,
                role=MessageRole.PENDING_ANSWER,
                confidence=1.0,
                entities=EntitySet(quantity=quantity, raw_text=raw),
                reasoning_code="pending_quantity_rule",
            )
        if expected == IntentType.PROVIDE_FULFILMENT_METHOD:
            method = self._fulfilment(normalized)
            if method is None:
                return None
            return Intent(
                type=expected,
                role=MessageRole.PENDING_ANSWER,
                confidence=1.0,
                entities=EntitySet(fulfilment_method=method, raw_text=raw),
                reasoning_code="pending_fulfilment_rule",
            )
        if expected == IntentType.PROVIDE_DELIVERY_DETAILS:
            if self._looks_like_question(normalized) or len(raw.strip()) < 5:
                return None
            return Intent(
                type=expected,
                role=MessageRole.PENDING_ANSWER,
                confidence=0.9,
                entities=EntitySet(delivery_details=raw.strip(), raw_text=raw),
                reasoning_code="pending_delivery_rule",
            )
        if expected == IntentType.PROVIDE_DATE and entities.preferred_date is not None:
            return Intent(
                type=expected,
                role=MessageRole.PENDING_ANSWER,
                confidence=1.0,
                entities=EntitySet(preferred_date=entities.preferred_date, raw_text=raw),
                reasoning_code="pending_date_rule",
            )
        if expected == IntentType.SELECT_TIME:
            selection = entities.selection
            if entities.start_time is None and selection is None:
                return None
            return Intent(
                type=expected,
                role=MessageRole.PENDING_ANSWER,
                confidence=0.99,
                entities=EntitySet(
                    selection=selection,
                    start_time=entities.start_time,
                    raw_text=raw,
                ),
                reasoning_code="pending_time_rule",
            )
        if expected == IntentType.SELECT_STAFF:
            allow_skip = question is not None and question.metadata.get("allow_skip") is True
            if allow_skip and normalized in {
                "skip",
                "any",
                "anyone",
                "no preference",
                "business can choose",
            }:
                return Intent(
                    type=expected,
                    role=MessageRole.PENDING_ANSWER,
                    confidence=1.0,
                    entities=EntitySet(raw_text=raw, extras={"skip_staff": True}),
                    reasoning_code="pending_staff_skip_rule",
                )
            selection = self._match_selection(raw, entities, question)
            if selection is None:
                return None
            return Intent(
                type=expected,
                role=MessageRole.PENDING_ANSWER,
                confidence=0.99,
                entities=EntitySet(selection=selection, raw_text=raw),
                reasoning_code="pending_staff_rule",
            )
        if expected == IntentType.PROVIDE_CUSTOMER_DETAILS:
            if entities.contact_number is None or self._looks_like_question(normalized):
                return None
            name = self._name_without_phone(raw)
            if len(name) < 2:
                return None
            return Intent(
                type=expected,
                role=MessageRole.PENDING_ANSWER,
                confidence=0.95,
                entities=EntitySet(
                    customer_name=name,
                    contact_number=entities.contact_number,
                    raw_text=raw,
                ),
                reasoning_code="pending_customer_rule",
            )
        if expected == IntentType.CONFIRM and normalized in {
            "yes",
            "y",
            "confirm",
            "confirmed",
            "submit",
            "ok",
            "okay",
        }:
            return Intent(
                type=expected,
                role=MessageRole.PENDING_ANSWER,
                confidence=1.0,
                entities=EntitySet(raw_text=raw),
                reasoning_code="pending_confirmation_rule",
            )
        return None

    def _safe_interruption(
        self,
        normalized: str,
        raw: str,
        entities: EntitySet,
        session: Session,
    ) -> Intent | None:
        if session.flow not in {Flow.CATALOGUE, Flow.ORDER, Flow.BOOKING}:
            return None
        if self._loyalty_question(normalized):
            return Intent(
                type=IntentType.LOYALTY_STATUS,
                role=MessageRole.SAFE_INTERRUPTION,
                confidence=0.98,
                entities=EntitySet(raw_text=raw),
                reasoning_code="safe_loyalty_interruption",
            )
        if self._hours_question(normalized):
            return Intent(
                type=IntentType.BUSINESS_HOURS,
                role=MessageRole.SAFE_INTERRUPTION,
                confidence=0.99,
                entities=EntitySet(raw_text=raw),
                reasoning_code="safe_hours_interruption",
            )
        if self._business_info_question(normalized):
            return Intent(
                type=IntentType.BUSINESS_INFO,
                role=MessageRole.SAFE_INTERRUPTION,
                confidence=0.98,
                entities=EntitySet(raw_text=raw),
                reasoning_code="safe_business_info_interruption",
            )
        if self._looks_like_question(normalized):
            return Intent(
                type=IntentType.FAQ,
                role=MessageRole.SAFE_INTERRUPTION,
                confidence=0.75,
                entities=EntitySet(query=raw, raw_text=raw),
                reasoning_code="safe_faq_interruption",
            )
        return None

    def _new_request(
        self,
        normalized: str,
        raw: str,
        entities: EntitySet,
        session: Session,
    ) -> Intent | None:
        if self._loyalty_question(normalized):
            return Intent(
                type=IntentType.LOYALTY_STATUS,
                role=MessageRole.NEW_REQUEST,
                confidence=0.98,
                entities=EntitySet(raw_text=raw),
                reasoning_code="loyalty_status_rule",
            )
        if self._hours_question(normalized):
            return Intent(
                type=IntentType.BUSINESS_HOURS,
                role=MessageRole.NEW_REQUEST,
                confidence=0.99,
                entities=EntitySet(raw_text=raw),
                reasoning_code="business_hours_rule",
            )
        if self._business_info_question(normalized):
            return Intent(
                type=IntentType.BUSINESS_INFO,
                role=MessageRole.NEW_REQUEST,
                confidence=0.98,
                entities=EntitySet(raw_text=raw),
                reasoning_code="business_info_rule",
            )
        if _contains_any(normalized, ("book", "appointment", "schedule")):
            return Intent(
                type=IntentType.START_BOOKING,
                role=MessageRole.NEW_REQUEST,
                confidence=0.94,
                entities=EntitySet(
                    query=raw,
                    item_type=ItemType.SERVICE,
                    preferred_date=entities.preferred_date,
                    start_time=entities.start_time,
                    raw_text=raw,
                ),
                reasoning_code="booking_request_rule",
            )
        if _contains_any(normalized, ("buy", "order", "purchase")) or (
            "deliver" in normalized and session.flow == Flow.IDLE
        ):
            return Intent(
                type=IntentType.START_ORDER,
                role=MessageRole.NEW_REQUEST,
                confidence=0.94,
                entities=EntitySet(
                    query=_catalogue_query(raw),
                    quantity=entities.quantity,
                    fulfilment_method=self._fulfilment(normalized),
                    brand=entities.brand,
                    relative_size=entities.relative_size,
                    barcode=entities.barcode,
                    raw_text=raw,
                ),
                reasoning_code="order_request_rule",
            )
        if _contains_any(
            normalized,
            (
                "catalog",
                "catalogue",
                "product",
                "service",
                "price",
                "do you have",
                "available",
                "show me",
                "find",
            ),
        ):
            return Intent(
                type=IntentType.CATALOGUE_SEARCH,
                role=MessageRole.NEW_REQUEST,
                confidence=0.87,
                entities=EntitySet(
                    query=_catalogue_query(raw),
                    relative_size=entities.relative_size,
                    barcode=entities.barcode,
                    raw_text=raw,
                ),
                reasoning_code="catalogue_search_rule",
            )
        if self._looks_like_question(normalized):
            return Intent(
                type=IntentType.FAQ,
                role=MessageRole.NEW_REQUEST,
                confidence=0.72,
                entities=EntitySet(query=raw, raw_text=raw),
                reasoning_code="faq_question_rule",
            )
        return None

    @staticmethod
    def _extract_entities(raw: str) -> EntitySet:
        preferred_date: date | None = None
        date_match = _DATE_PATTERN.search(raw)
        if date_match:
            try:
                preferred_date = date.fromisoformat(date_match.group(1))
            except ValueError:
                preferred_date = None

        start_time: time | None = None
        time_match = _TIME_PATTERN.search(raw)
        if time_match:
            start_time = time(int(time_match.group(1)), int(time_match.group(2)))

        contact: str | None = None
        phone_match = _PHONE_PATTERN.search(raw)
        if phone_match:
            contact = "".join(
                character for character in phone_match.group(0) if character.isdigit()
            )

        quantity: int | None = None
        quantity_text = raw
        for pattern in (
            _DATE_PATTERN,
            _TIME_PATTERN,
            _PHONE_PATTERN,
            _BARCODE_PATTERN,
            _SIZE_PATTERN,
        ):
            quantity_text = pattern.sub(" ", quantity_text)
        number_match = _INTEGER_PATTERN.search(quantity_text)
        if number_match:
            value = int(number_match.group(1))
            if value > 0:
                quantity = value

        barcode: str | None = None
        barcode_match = _BARCODE_PATTERN.search(raw)
        if barcode_match:
            barcode = barcode_match.group(1)

        relative_size: RelativeSize | None = None
        normalized = _normalize(raw)
        for term, relative_value in (
            ("smallest", RelativeSize.SMALLEST),
            ("largest", RelativeSize.LARGEST),
            ("small", RelativeSize.SMALL),
            ("medium", RelativeSize.MEDIUM),
            ("large", RelativeSize.LARGE),
        ):
            if re.search(rf"\b{term}\b", normalized):
                relative_size = relative_value
                break

        selection: str | int | None = None
        stripped = raw.strip()
        if stripped.isdigit() and len(stripped) <= 3:
            selection = int(stripped)
        elif _SIZE_PATTERN.fullmatch(stripped):
            selection = stripped.lower().replace(" ", "")

        return EntitySet(
            selection=selection,
            quantity=quantity,
            fulfilment_method=HybridInterpreter._fulfilment(normalized),
            preferred_date=preferred_date,
            start_time=start_time,
            contact_number=contact,
            relative_size=relative_size,
            barcode=barcode,
            raw_text=raw,
        )

    @staticmethod
    def _word_quantity(normalized: str) -> int | None:
        quantities = {
            "one": 1,
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
            "six": 6,
            "seven": 7,
            "eight": 8,
            "nine": 9,
            "ten": 10,
        }
        return quantities.get(normalized.strip())

    @staticmethod
    def _fulfilment(normalized: str) -> FulfilmentMethod | None:
        if "deliver" in normalized or "delivery" in normalized:
            return FulfilmentMethod.DELIVERY
        if _contains_any(normalized, ("collect", "collection", "pickup", "pick up")):
            return FulfilmentMethod.COLLECTION
        return None

    @staticmethod
    def _correction_field(normalized: str) -> str | None:
        mapping = (
            (("product", "item"), "product"),
            (("quantity", "amount", "number"), "quantity"),
            (("deliver", "collect", "fulfil"), "fulfilment_method"),
            (("address", "location", "direction"), "delivery_details"),
            (("service",), "service"),
            (("date", "day"), "preferred_date"),
            (("time", "slot"), "time"),
            (("staff", "stylist", "barber"), "staff"),
            (("name", "phone", "contact"), "customer_details"),
        )
        for terms, field in mapping:
            if any(term in normalized for term in terms):
                return field
        return None

    @staticmethod
    def _match_selection(
        raw: str,
        entities: EntitySet,
        question: PendingQuestion | None,
    ) -> str | int | None:
        if entities.selection is not None:
            return entities.selection
        cleaned = raw.strip()
        if question is None:
            return None
        options = question.metadata.get("options", ())
        if not isinstance(options, (list, tuple)):
            return None
        normalized = cleaned.lower().replace(" ", "")
        allow_confirmation = question.metadata.get("allow_confirmation", False)
        if allow_confirmation is True and normalized in {
            "yes",
            "y",
            "yeah",
            "yep",
            "confirm",
            "correct",
            "thatone",
            "thisone",
        }:
            return cleaned
        for option in options:
            option_text = str(option).strip()
            if normalized == option_text.lower().replace(" ", ""):
                return option_text
        return None

    @staticmethod
    def _name_without_phone(raw: str) -> str:
        without_phone = _PHONE_PATTERN.sub("", raw)
        return without_phone.strip(" ,;-")

    @staticmethod
    def _looks_like_question(normalized: str) -> bool:
        question_starters = (
            "what",
            "where",
            "when",
            "why",
            "how",
            "can",
            "could",
            "do",
            "does",
            "is",
            "are",
        )
        return normalized.endswith("?") or any(
            normalized == starter or normalized.startswith(f"{starter} ")
            for starter in question_starters
        )

    @staticmethod
    def _loyalty_question(normalized: str) -> bool:
        return _contains_any(
            normalized,
            (
                "loyalty",
                "loyalty points",
                "my points",
                "reward points",
                "my tier",
                "loyalty tier",
                "my reward",
            ),
        )

    @staticmethod
    def _hours_question(normalized: str) -> bool:
        return _contains_any(
            normalized,
            (
                "open now",
                "opening time",
                "closing time",
                "what time do you close",
                "what time do you open",
                "business hours",
                "your hours",
                "hours today",
                "today's hours",
                "are you open",
            ),
        )

    @staticmethod
    def _business_info_question(normalized: str) -> bool:
        return _contains_any(
            normalized,
            (
                "where are you",
                "your location",
                "business address",
                "contact number",
                "phone number",
                "business name",
            ),
        )

    @staticmethod
    def _clarify(raw: str, code: str) -> Intent:
        return Intent(
            type=IntentType.CLARIFY,
            role=MessageRole.UNKNOWN,
            confidence=0.0,
            entities=EntitySet(raw_text=raw),
            reasoning_code=code,
        )
