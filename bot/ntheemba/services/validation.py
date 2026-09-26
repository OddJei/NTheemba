"""Validation boundary for rule- and model-produced intent proposals."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from datetime import date, time
from enum import Enum
from typing import Any

from ntheemba.domain.enums import (
    FulfilmentMethod,
    IntentType,
    ItemType,
    MessageRole,
    RelativeSize,
)
from ntheemba.domain.intents import EntitySet, Intent


class InterpretationValidationError(ValueError):
    """Raised when an interpretation proposal is structurally unsafe."""


_RESTRICTED_ENTITY_KEYS = frozenset(
    {
        "available",
        "availability",
        "available_quantity",
        "business_product_id",
        "currency",
        "idempotency_key",
        "ncpc_product_id",
        "price",
        "request_id",
        "selling_price",
        "service_id",
        "slot_id",
        "stock",
        "total",
    }
)

_ALLOWED_ENTITY_KEYS = frozenset(
    {
        "barcode",
        "brand",
        "contact_number",
        "customer_name",
        "delivery_details",
        "extras",
        "fulfilment_method",
        "item_type",
        "preferred_date",
        "product_family",
        "quantity",
        "query",
        "raw_text",
        "relative_size",
        "selection",
        "staff_id",
        "start_time",
        "variant",
    }
)


def _bounded_text(value: Any, *, field: str, maximum: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise InterpretationValidationError(f"{field} must be text")
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > maximum:
        raise InterpretationValidationError(f"{field} is too long")
    return cleaned


def _optional_int(value: Any, *, field: str) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise InterpretationValidationError(f"{field} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise InterpretationValidationError(f"{field} must be an integer") from error
    return parsed


def _parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise InterpretationValidationError("preferred_date must be an ISO date")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise InterpretationValidationError("preferred_date must be YYYY-MM-DD") from error


def _parse_time(value: Any) -> time | None:
    if value is None or value == "":
        return None
    if isinstance(value, time):
        return value
    if not isinstance(value, str):
        raise InterpretationValidationError("start_time must be a time")
    normalized = value.strip()
    if len(normalized) == 5:
        normalized = f"{normalized}:00"
    try:
        return time.fromisoformat(normalized)
    except ValueError as error:
        raise InterpretationValidationError("start_time must be HH:MM") from error


def _parse_enum[EnumT: Enum](
    value: Any,
    enum_type: type[EnumT],
    *,
    field: str,
) -> EnumT | None:
    if value is None or value == "":
        return None
    try:
        return enum_type(str(value).strip().lower())
    except ValueError as error:
        raise InterpretationValidationError(f"unsupported {field}") from error


def _parse_selection(value: Any) -> str | int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise InterpretationValidationError("selection must be text or an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        if len(cleaned) > 200:
            raise InterpretationValidationError("selection is too long")
        return cleaned
    raise InterpretationValidationError("selection must be text or an integer")


def _parse_extras(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise InterpretationValidationError("extras must be an object")
    extras = dict(value)
    normalized = {str(key).strip().lower() for key in extras}
    restricted = normalized & _RESTRICTED_ENTITY_KEYS
    if restricted:
        name = sorted(restricted)[0]
        raise InterpretationValidationError(
            f"model output cannot assert external business fact {name!r}"
        )
    if len(extras) > 20:
        raise InterpretationValidationError("extras contains too many fields")
    return extras


def validate_intent(intent: Intent) -> Intent:
    """Validate an already typed intent and return it unchanged."""

    if intent.type == IntentType.UNKNOWN and intent.confidence > 0.5:
        raise InterpretationValidationError("unknown intent cannot have high confidence")
    if intent.role == MessageRole.PENDING_ANSWER and not intent.entities.raw_text:
        raise InterpretationValidationError("pending answers must preserve raw_text")
    restricted = {str(key).lower() for key in intent.entities.extras} & _RESTRICTED_ENTITY_KEYS
    if restricted:
        raise InterpretationValidationError("intent extras contain external business facts")
    return intent


class ModelOutputValidator:
    """Convert an untrusted model payload into one safe typed Intent."""

    def __init__(self, *, minimum_confidence: float = 0.62) -> None:
        if not 0 <= minimum_confidence <= 1:
            raise ValueError("minimum_confidence must be between zero and one")
        self.minimum_confidence = minimum_confidence

    def validate(
        self,
        payload: Any,
        *,
        raw_text: str,
        allowed_actions: Collection[IntentType] | None = None,
    ) -> Intent:
        """Validate shape, enums, confidence, entities, and restricted facts."""

        if not isinstance(payload, Mapping):
            raise InterpretationValidationError("model output must be an object")

        intent_value = payload.get("intent", payload.get("action"))
        role_value = payload.get("role", MessageRole.NEW_REQUEST.value)
        try:
            intent_type = IntentType(str(intent_value).strip().lower())
        except (TypeError, ValueError) as error:
            raise InterpretationValidationError("model proposed an unsupported intent") from error
        if allowed_actions is not None and intent_type not in allowed_actions:
            raise InterpretationValidationError("model proposed an unavailable action")
        try:
            role = MessageRole(str(role_value).strip().lower())
        except (TypeError, ValueError) as error:
            raise InterpretationValidationError(
                "model proposed an unsupported message role"
            ) from error

        try:
            confidence = float(payload.get("confidence", 0.0))
        except (TypeError, ValueError) as error:
            raise InterpretationValidationError("confidence must be numeric") from error
        if not 0 <= confidence <= 1:
            raise InterpretationValidationError("confidence must be between zero and one")

        entities_payload = payload.get("entities") or {}
        if not isinstance(entities_payload, Mapping):
            raise InterpretationValidationError("entities must be an object")
        direct_restricted = {str(key).lower() for key in entities_payload} & _RESTRICTED_ENTITY_KEYS
        if direct_restricted:
            name = sorted(direct_restricted)[0]
            raise InterpretationValidationError(
                f"model output cannot assert external business fact {name!r}"
            )
        unknown = {str(key) for key in entities_payload} - _ALLOWED_ENTITY_KEYS
        if unknown:
            raise InterpretationValidationError(f"unsupported entity field {sorted(unknown)[0]!r}")

        if confidence < self.minimum_confidence:
            return Intent(
                type=IntentType.CLARIFY,
                role=MessageRole.UNKNOWN,
                confidence=confidence,
                entities=EntitySet(raw_text=raw_text),
                reasoning_code="model_confidence_below_threshold",
            )

        quantity = _optional_int(entities_payload.get("quantity"), field="quantity")
        entities = EntitySet(
            query=_bounded_text(entities_payload.get("query"), field="query", maximum=500),
            selection=_parse_selection(entities_payload.get("selection")),
            quantity=quantity,
            fulfilment_method=_parse_enum(
                entities_payload.get("fulfilment_method"),
                FulfilmentMethod,
                field="fulfilment_method",
            ),
            delivery_details=_bounded_text(
                entities_payload.get("delivery_details"),
                field="delivery_details",
                maximum=1000,
            ),
            preferred_date=_parse_date(entities_payload.get("preferred_date")),
            start_time=_parse_time(entities_payload.get("start_time")),
            staff_id=_bounded_text(entities_payload.get("staff_id"), field="staff_id", maximum=120),
            customer_name=_bounded_text(
                entities_payload.get("customer_name"),
                field="customer_name",
                maximum=120,
            ),
            contact_number=_bounded_text(
                entities_payload.get("contact_number"),
                field="contact_number",
                maximum=30,
            ),
            item_type=_parse_enum(entities_payload.get("item_type"), ItemType, field="item_type"),
            brand=_bounded_text(entities_payload.get("brand"), field="brand", maximum=120),
            product_family=_bounded_text(
                entities_payload.get("product_family"),
                field="product_family",
                maximum=160,
            ),
            variant=_bounded_text(entities_payload.get("variant"), field="variant", maximum=160),
            relative_size=_parse_enum(
                entities_payload.get("relative_size"),
                RelativeSize,
                field="relative_size",
            ),
            barcode=_bounded_text(entities_payload.get("barcode"), field="barcode", maximum=80),
            raw_text=raw_text,
            extras=_parse_extras(entities_payload.get("extras")),
        )
        reasoning_code = (
            _bounded_text(payload.get("reasoning_code"), field="reasoning_code", maximum=120)
            or "model_validated"
        )
        return validate_intent(
            Intent(
                type=intent_type,
                role=role,
                confidence=confidence,
                entities=entities,
                reasoning_code=reasoning_code,
            )
        )
