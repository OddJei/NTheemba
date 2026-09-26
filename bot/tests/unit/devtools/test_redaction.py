"""Tests for developer-tooling trace redaction."""

from __future__ import annotations

from ntheemba.devtools.redaction import REDACTED, redact_mapping


def test_redacts_secret_like_keys_recursively() -> None:
    result = redact_mapping(
        {
            "intent": "catalogue",
            "api_key": "key-value",
            "nested": {
                "authorization": "Bearer secret",
                "password_hint": "still-sensitive",
            },
        }
    )

    assert result == {
        "intent": "catalogue",
        "api_key": REDACTED,
        "nested": {
            "authorization": REDACTED,
            "password_hint": REDACTED,
        },
    }


def test_bounds_long_text_and_binary_values() -> None:
    result = redact_mapping({"description": "x" * 700, "payload": b"abc"})

    assert result["description"].endswith("…[TRUNCATED]")
    assert result["payload"] == "[BYTES:3]"
