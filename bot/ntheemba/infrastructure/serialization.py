"""Versioned, allow-listed JSON serialization for durable runtime state."""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from types import UnionType
from typing import Any, TypeVar, Union, cast, get_args, get_origin, get_type_hints

from ntheemba.domain.booking_draft import (
    AppointmentSlot,
    BookingDraft,
    BookingStaffOption,
    ServiceSelection,
)
from ntheemba.domain.intents import EntitySet, Intent, PendingQuestion
from ntheemba.domain.marketplace import MarketplaceProductOffer, MarketplaceProductSearch
from ntheemba.domain.order_draft import OrderDraft, PriceSnapshot
from ntheemba.domain.platform_session import PlatformConversationSession
from ntheemba.domain.product_resolution import (
    ProductCandidate,
    ProductQuery,
    ProductResolution,
    ResolvedProduct,
)
from ntheemba.domain.session import ConversationTurn, Session, SuspendedState

T = TypeVar("T")


class SerializationError(ValueError):
    """Raised when durable state cannot be safely encoded or decoded."""


_ALLOWED_DATACLASSES = {
    cls.__name__: cls
    for cls in (
        AppointmentSlot,
        BookingDraft,
        BookingStaffOption,
        ConversationTurn,
        EntitySet,
        Intent,
        OrderDraft,
        PendingQuestion,
        MarketplaceProductOffer,
        MarketplaceProductSearch,
        PlatformConversationSession,
        PriceSnapshot,
        ProductCandidate,
        ProductQuery,
        ProductResolution,
        ResolvedProduct,
        ServiceSelection,
        Session,
        SuspendedState,
    )
}

_ALLOWED_ENUMS: dict[str, type[Enum]] = {}
for module_name in (
    "ntheemba.domain.enums",
    "ntheemba.domain.platform_session",
    "ntheemba.ports.idempotency",
):
    module = __import__(module_name, fromlist=["*"])
    for candidate in vars(module).values():
        if isinstance(candidate, type) and issubclass(candidate, Enum):
            _ALLOWED_ENUMS[candidate.__name__] = candidate


class TaggedJsonCodec:
    """Encode trusted application dataclasses into versioned JSON documents."""

    def __init__(self, *, schema_name: str, version: int = 1) -> None:
        if not schema_name.strip():
            raise ValueError("schema_name must not be empty")
        if version <= 0:
            raise ValueError("version must be greater than zero")
        self.schema_name = schema_name.strip()
        self.version = version

    def dumps(self, value: object) -> bytes:
        envelope = {
            "schema": self.schema_name,
            "version": self.version,
            "payload": self._encode(value),
        }
        try:
            return json.dumps(
                envelope,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        except (TypeError, ValueError) as error:
            raise SerializationError("value could not be encoded") from error

    def loads(self, payload: bytes | str, expected_type: type[T]) -> T:
        try:
            raw = payload.decode("utf-8") if isinstance(payload, bytes) else payload
            envelope = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise SerializationError("payload is not valid UTF-8 JSON") from error
        if not isinstance(envelope, dict):
            raise SerializationError("payload envelope must be an object")
        if envelope.get("schema") != self.schema_name:
            raise SerializationError("payload schema does not match")
        if envelope.get("version") != self.version:
            raise SerializationError("payload version is not supported")
        decoded = self._decode(envelope.get("payload"))
        if not isinstance(decoded, expected_type):
            raise SerializationError(
                f"decoded payload is not {expected_type.__name__}"
            )
        return decoded

    def _encode(self, value: object) -> object:
        if value is None:
            return value
        if isinstance(value, Enum):
            enum_name = type(value).__name__
            if enum_name not in _ALLOWED_ENUMS:
                raise SerializationError(f"enum {enum_name} is not allow-listed")
            return {"$type": "enum", "name": enum_name, "value": value.value}
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, Decimal):
            return {"$type": "decimal", "value": str(value)}
        if isinstance(value, datetime):
            if value.tzinfo is None:
                raise SerializationError("datetime values must be timezone-aware")
            return {"$type": "datetime", "value": value.isoformat()}
        if isinstance(value, date):
            return {"$type": "date", "value": value.isoformat()}
        if isinstance(value, time):
            return {"$type": "time", "value": value.isoformat()}
        if isinstance(value, bytes):
            return {
                "$type": "bytes",
                "value": base64.b64encode(value).decode("ascii"),
            }
        if is_dataclass(value) and not isinstance(value, type):
            class_name = type(value).__name__
            if class_name not in _ALLOWED_DATACLASSES:
                raise SerializationError(f"dataclass {class_name} is not allow-listed")
            return {
                "$type": "dataclass",
                "name": class_name,
                "fields": {
                    field.name: self._encode(getattr(value, field.name))
                    for field in fields(value)
                },
            }
        if isinstance(value, Mapping):
            return {
                "$type": "mapping",
                "items": [
                    [self._encode(key), self._encode(item)]
                    for key, item in value.items()
                ],
            }
        if isinstance(value, frozenset):
            return {"$type": "frozenset", "items": [self._encode(item) for item in value]}
        if isinstance(value, tuple):
            return {"$type": "tuple", "items": [self._encode(item) for item in value]}
        if isinstance(value, Sequence):
            return {"$type": "list", "items": [self._encode(item) for item in value]}
        raise SerializationError(f"unsupported value type: {type(value).__name__}")

    def _decode(self, value: object) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if not isinstance(value, dict):
            raise SerializationError("tagged value must be an object")
        tag = value.get("$type")
        if tag == "decimal":
            return Decimal(self._string_value(value))
        if tag == "datetime":
            parsed = datetime.fromisoformat(self._string_value(value))
            if parsed.tzinfo is None:
                raise SerializationError("decoded datetime is not timezone-aware")
            return parsed
        if tag == "date":
            return date.fromisoformat(self._string_value(value))
        if tag == "time":
            return time.fromisoformat(self._string_value(value))
        if tag == "bytes":
            try:
                return base64.b64decode(self._string_value(value), validate=True)
            except ValueError as error:
                raise SerializationError("invalid base64 payload") from error
        if tag == "enum":
            name = self._string_field(value, "name")
            enum_type = _ALLOWED_ENUMS.get(name)
            if enum_type is None:
                raise SerializationError(f"enum {name} is not allow-listed")
            try:
                return enum_type(value.get("value"))
            except ValueError as error:
                raise SerializationError(f"invalid {name} value") from error
        if tag == "dataclass":
            name = self._string_field(value, "name")
            class_type = _ALLOWED_DATACLASSES.get(name)
            if class_type is None:
                raise SerializationError(f"dataclass {name} is not allow-listed")
            raw_fields = value.get("fields")
            if not isinstance(raw_fields, dict):
                raise SerializationError("dataclass fields must be an object")
            expected_fields = {item.name for item in fields(class_type)}
            if set(raw_fields) != expected_fields:
                raise SerializationError(f"dataclass fields do not match {name}")
            try:
                type_hints = get_type_hints(class_type)
                kwargs = {
                    key: _coerce_legacy_enums(
                        self._decode(item),
                        type_hints.get(key, Any),
                    )
                    for key, item in raw_fields.items()
                }
                return class_type(**kwargs)
            except (TypeError, ValueError) as error:
                raise SerializationError(f"invalid {name} payload") from error
        if tag in {"list", "tuple", "frozenset"}:
            items = value.get("items")
            if not isinstance(items, list):
                raise SerializationError(f"{tag} items must be a list")
            decoded = [self._decode(item) for item in items]
            if tag == "tuple":
                return tuple(decoded)
            if tag == "frozenset":
                return frozenset(decoded)
            return decoded
        if tag == "mapping":
            items = value.get("items")
            if not isinstance(items, list):
                raise SerializationError("mapping items must be a list")
            result: dict[Any, Any] = {}
            for pair in items:
                if not isinstance(pair, list) or len(pair) != 2:
                    raise SerializationError("mapping entries must be two-item lists")
                result[self._decode(pair[0])] = self._decode(pair[1])
            return result
        raise SerializationError("unknown tagged value type")

    @staticmethod
    def _string_value(value: Mapping[str, object]) -> str:
        return TaggedJsonCodec._string_field(value, "value")

    @staticmethod
    def _string_field(value: Mapping[str, object], field_name: str) -> str:
        field_value = value.get(field_name)
        if not isinstance(field_value, str):
            raise SerializationError(f"{field_name} must be a string")
        return field_value


def _coerce_legacy_enums(value: Any, annotation: Any) -> Any:
    """Restore enums from early v1 payloads that encoded StrEnum as strings."""

    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return value if isinstance(value, annotation) else annotation(value)

    origin = get_origin(annotation)
    arguments = get_args(annotation)
    if origin in {Union, UnionType}:
        enum_type = next(
            (
                item
                for item in arguments
                if isinstance(item, type) and issubclass(item, Enum)
            ),
            None,
        )
        if enum_type is not None and value is not None:
            return value if isinstance(value, enum_type) else enum_type(value)
        return value

    if origin in {list, tuple, set, frozenset} and arguments:
        item_type = arguments[0]
        converted = (_coerce_legacy_enums(item, item_type) for item in value)
        if origin is tuple:
            return tuple(converted)
        if origin is frozenset:
            return frozenset(converted)
        if origin is set:
            return set(converted)
        return list(converted)

    return value


SESSION_CODEC = TaggedJsonCodec(schema_name="ntheemba.session", version=1)
PLATFORM_SESSION_CODEC = TaggedJsonCodec(schema_name="ntheemba.platform-session", version=1)
IDEMPOTENCY_CODEC = TaggedJsonCodec(schema_name="ntheemba.idempotency", version=1)


def decode_session(payload: bytes | str) -> Session:
    return SESSION_CODEC.loads(payload, Session)


def encode_session(session: Session) -> bytes:
    return SESSION_CODEC.dumps(session)


def decode_platform_session(payload: bytes | str) -> PlatformConversationSession:
    return PLATFORM_SESSION_CODEC.loads(payload, PlatformConversationSession)


def encode_platform_session(session: PlatformConversationSession) -> bytes:
    return PLATFORM_SESSION_CODEC.dumps(session)


def cast_mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SerializationError("value must be a mapping")
    return cast(Mapping[str, Any], value)
