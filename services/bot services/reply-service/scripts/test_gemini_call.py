from __future__ import annotations

import asyncio
import os
import json
import sys

import sys
import os
import pathlib

# If no REPLY_GEMINI_API_KEY is set, prefer the intent service config env vars
# so this script can reuse the existing intent-service Gemini settings.
if not os.getenv("REPLY_GEMINI_API_KEY"):
    intent_key = os.getenv("INTENT_GEMINI_API_KEY") or os.getenv("gemini_key")
    if intent_key:
        os.environ["REPLY_GEMINI_API_KEY"] = intent_key
    intent_model = os.getenv("INTENT_GEMINI_MODEL") or os.getenv("gemini_model")
    if intent_model and not os.getenv("REPLY_GEMINI_MODEL"):
        os.environ["REPLY_GEMINI_MODEL"] = intent_model

# Ensure project root is on sys.path so `app` package can be imported when running this script directly.
root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

# Load .env if present so REPLY_GEMINI_* vars are available
try:
    from dotenv import load_dotenv
    load_dotenv(root.joinpath('.env'))
except Exception:
    pass

from app.core.config import get_settings
from app.services.gemini_client import GeminiClient
from app.services.renderer import _extract_gemini_text


async def main():
    settings = get_settings()
    if not settings.gemini.api_key:
        print("No REPLY_GEMINI_API_KEY configured. Set the env and retry.")
        return 1

    client = GeminiClient()

    instruction = (
        "You MUST return exactly one JSON object with a single key 'text'. No extra prose."
    )

    parts = [
        {"text": instruction},
        {"text": "Persona name: NTheemba"},
        {"text": "Business name: Kitwe Solar"},
        {"text": "Draft reply to improve (keep meaning): NTheemba at Kitwe Solar: Added 2 × Solar Panel A to your cart. Confirm checkout?"},
    ]

    payload = {
        "maxOutputTokens": int(settings.gemini.max_output_tokens),
        "prompt": {"messages": [{"role": "user", "content": {"parts": parts}}]},
    }

    try:
        resp = await client.generate_content(payload=payload, model=None)
        print("RAW RESPONSE:\n", json.dumps(resp, indent=2))
        parsed = _extract_gemini_text(resp) or "(no parsed text)"
        print("\nPARSED TEXT:\n", parsed)
        return 0
    except Exception as e:
        print("Error calling Gemini:", e)
        return 2


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
