"""Bounded redaction for values exposed by developer tooling."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

REDACTED = "[REDACTED]"
_MAX_DEPTH = 5
_MAX_ITEMS = 50
_MAX_TEXT_LENGTH = 500
_SENSITIVE_KEY_PARTS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "cookie",
        "credential",
        "cost",
        "deployment",
        "password",
        "phone",
        "private",
        "private_key",
        "raw",
        "secret",
        "session_token",
        "sheet_id",
        "spreadsheet",
        "supplier",
        "token",
    }
)


def redact_mapping(values: Mapping[str, Any]) -> dict[str, Any]:
    """Return a JSON-friendly copy with secret-like keys redacted and values bounded."""

    return {
        str(key): _redact_value(value, key=str(key), depth=0)
        for key, value in list(values.items())[:_MAX_ITEMS]
    }


def _redact_value(value: Any, *, key: str, depth: int) -> Any:
    if _is_sensitive_key(key):
        return REDACTED
    if depth >= _MAX_DEPTH:
        return "[MAX_DEPTH]"
    if isinstance(value, Mapping):
        return {
            str(nested_key): _redact_value(
                nested_value,
                key=str(nested_key),
                depth=depth + 1,
            )
            for nested_key, nested_value in list(value.items())[:_MAX_ITEMS]
        }
    if isinstance(value, str):
        if len(value) <= _MAX_TEXT_LENGTH:
            return value
        return f"{value[:_MAX_TEXT_LENGTH]}…[TRUNCATED]"
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_redact_value(item, key=key, depth=depth + 1) for item in list(value)[:_MAX_ITEMS]]
    if isinstance(value, bytes):
        return f"[BYTES:{len(value)}]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:_MAX_TEXT_LENGTH]


def _is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower().replace("-", "_").replace(" ", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)
