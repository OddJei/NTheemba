"""Tests for the built-in observability self-check."""

from __future__ import annotations

import pytest
from ntheemba.observability.self_check import run_observability_self_check


@pytest.mark.asyncio
async def test_self_check_emits_and_validates_nested_trace() -> None:
    result = await run_observability_self_check()

    assert result.status == "passed"
    assert result.event_count == 4
    assert result.validation.valid is True
    assert result.validation.complete is True
