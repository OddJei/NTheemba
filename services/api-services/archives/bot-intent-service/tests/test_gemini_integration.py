from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Ensure `app` package is importable when running pytest from the service folder.
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core import config as config_mod
from app.models.schemas import IntentRequest
from app.services.intent_service import service


@pytest.mark.asyncio
async def test_gemini_optional_call_real_api():
    """Optional integration test.

    This test can hit the real Gemini API and may incur cost.

    To run intentionally:
      - set RUN_GEMINI_TESTS=True
      - set INTENT_GEMINI_API_KEY (or gemini_key)
      - set INTENT_GEMINI_ENABLED=True

    If these are not set, the test is skipped.
    """

    if os.getenv("RUN_GEMINI_TESTS", "False") != "True":
        pytest.skip("Set RUN_GEMINI_TESTS=True to enable real Gemini integration test")

    # Ensure settings cache reflects current env.
    config_mod.get_settings.cache_clear()

    settings = config_mod.get_settings()
    if not (settings.gemini.enabled and settings.gemini.api_key):
        pytest.skip("Gemini not enabled or missing API key")

    # Reset client between tests.
    service._client = None

    req = IntentRequest(
        event_id="evt_gemini_1",
        session_id="sess_gemini_1",
        bot_id="bot_default",
        bot_type="default",
        raw_text="I want to buy 2 solar panels",
        enriched_meta={"current_node": "serve_products"},
    )

    res = await service.resolve(req)

    # Minimum guarantee: Gemini path was attempted and did not throw.
    assert res.diagnostics.get("gemini_attempted") is True
    assert "gemini_error" not in res.diagnostics

    # If parsing succeeds, we should see gemini as the chosen fallback.
    # If parsing fails, we still accept the call as successful, but it will remain deterministic.
    assert res.intent.id
