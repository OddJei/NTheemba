from __future__ import annotations

import os
import asyncio
from typing import Any
import random
import json

import httpx


async def _call_gemini(prompt: str, *, model: str | None = None, api_key: str | None = None, endpoint: str | None = None) -> str:
    # Resolve model/endpoint/api_key from env with sensible defaults used in this repo.
    model = (
        model
        or os.getenv("INTENT_GEMINI_MODEL")
        or os.getenv("GEMINI_MODEL")
        or os.getenv("INTENT_GEMINI_MODEL")
        or "gemini-3-flash-preview"
    )
    endpoint = (
        endpoint
        or os.getenv("GEMINI_API_ENDPOINT")
        or os.getenv("INTENT_GEMINI_API_ENDPOINT")
        or "https://generativelanguage.googleapis.com/v1beta/models"
    )

    # Support comma-separated API keys in env var lists; pick the first non-empty
    env_key = os.getenv("INTENT_GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("INTENT_GEMINI_API_KEY")
    if api_key:
        env_key = api_key
    api_key_val = None
    if env_key:
        api_key_val = next((k.strip() for k in env_key.split(",") if k.strip()), None)

    url = f"{endpoint.rstrip('/')}/{model}:generateContent"
    body = {"contents": [{"parts": [{"text": prompt}]}]}

    headers = {"Content-Type": "application/json"}
    if api_key_val:
        headers["x-goog-api-key"] = api_key_val

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, json=body, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    # Try common response shapes to extract text
    try:
        # genai-like client may return `candidates` with content parts
        if isinstance(data, dict):
            c = data.get("candidates") or data.get("candidates")
            if isinstance(c, list) and c:
                first = c[0]
                if isinstance(first, dict):
                    # `content` may be a dict with `parts` or a list of parts
                    cont = first.get("content") or first.get("output")
                    parts = None
                    if isinstance(cont, dict):
                        parts = cont.get("parts")
                    elif isinstance(cont, list):
                        # sometimes content is a list of parts directly
                        parts = cont
                    if parts and isinstance(parts, list):
                        part = parts[0]
                        if isinstance(part, dict) and part.get("text"):
                            return str(part.get("text"))
            # fallback: common `output` -> `contents` -> `parts` -> `text`
            out = data.get("output") or {}
            if isinstance(out, dict):
                contents = out.get("contents") or out.get("candidates")
                if isinstance(contents, list) and contents:
                    first = contents[0]
                    parts = first.get("parts") or []
                    if parts and isinstance(parts[0], dict) and parts[0].get("text"):
                        return str(parts[0].get("text"))
    except Exception:
        pass

    # As last resort, stringify the whole payload
    return str(data)


def _build_missing_slots_prompt(template_vars: dict[str, Any]) -> str:
    stage = template_vars.get("stage") or "chat"
    locale = template_vars.get("locale") or "en"
    missing = template_vars.get("missing_slots") or []
    ctas = template_vars.get("cta_labels") or []
    business = template_vars.get("business_name") or None
    bot = template_vars.get("bot_name") or None

    missing_list = ", ".join(missing) if isinstance(missing, list) else str(missing)
    cta_text = ", ".join(ctas[:3]) if isinstance(ctas, list) and ctas else ""

    header = f"You are a helpful shopping assistant for {business or 'the store'}." if business else "You are a helpful shopping assistant."
    tone = f"Keep the message friendly and concise (locale={locale})."
    ask = f"The user is in the '{stage}' stage. Ask explicitly for the following missing information: {missing_list}."
    if cta_text:
        ask += f" Offer quick action labels: {cta_text}."

    return "\n\n".join([header, tone, ask])


async def render_reply(template_id: str | None, template_vars: dict[str, Any]) -> str:
    """Render a reply using Gemini NLG. Returns the generated text or a conservative fallback.

    Only a simple, focused prompt builder is implemented — templates can be swapped later.
    """
    # Build a focused prompt for missing_slots or generic chat templates.
    # Enforce global persona and light Bemba/Nyanja mixing in the prompt so the
    # model follows the expected style for all replies.
    try:
        persona_instruction = (
            "You are NTheemba, a friendly, helpful shopping assistant persona. "
            "Keep responses concise, warm, and helpful."
        )

        mixing_instruction = (
            "Mix in Bemba and Nyanja phrases lightly across replies (about 10-20% "
            "of the output). Use short idiomatic phrases like 'Muli bwanji', 'Zikomo', "
            "'Natotela', or 'Tikulandira' where natural—do not replace core content."
        )

        # If a full context snapshot is provided, include it verbatim in the prompt
        context_snapshot = template_vars.get("context_snapshot")
        cs_text = None
        if context_snapshot is not None:
            try:
                cs_text = json.dumps(context_snapshot, indent=2, ensure_ascii=False)
            except Exception:
                cs_text = str(context_snapshot)

        # Always use the direct prompt pattern: include persona, mixing instruction,
        # the context snapshot (if provided) as explicit JSON, and an explicit
        # instruction telling the model what to produce. This makes outputs
        # consistent with direct LLM calls and centralizes post-processing.
        stage = template_vars.get("stage") or "chat"
        locale = template_vars.get("locale") or "en"
        bot = template_vars.get("bot_name") or "assistant"

        if template_vars.get("missing_slots"):
            task_instruction = _build_missing_slots_prompt(template_vars)
        else:
            task_instruction = (
                f"You are a helpful shopping assistant ({bot}). Produce a concise friendly reply for the user in {locale} for stage {stage}. "
                "Keep it short and actionable. Mention up to two suggested products when present and ask whether to add one to cart."
            )

        prompt_parts = [persona_instruction, mixing_instruction]
        if cs_text:
            prompt_parts.append("Context snapshot (JSON):")
            prompt_parts.append(cs_text)
        prompt_parts.append("Instruction:")
        prompt_parts.append(task_instruction)

        direct_prompt = "\n\n".join(prompt_parts)

        # Call Gemini with the explicit direct prompt and post-process the returned text
        text = await _call_gemini(direct_prompt)
        if isinstance(text, str) and text.strip():
            generated = text.strip()
            final = _apply_language_mix(generated, ratio_min=0.10, ratio_max=0.20)
            return final
    except Exception:
        pass

    # Fallback conservative messages
    if template_vars.get("missing_slots"):
        missing = template_vars.get("missing_slots") or []
        if missing:
            return _apply_language_mix("Please provide: " + ", ".join(missing) + ".")
    return _apply_language_mix(template_vars.get("fallback_text") or "Please provide the missing details to continue.")


def _apply_language_mix(text: str, *, ratio_min: float = 0.10, ratio_max: float = 0.20) -> str:
    """Inject short Bemba/Nyanja phrases into `text` to achieve ~ratio mix.

    This is a lightweight post-processor: it appends idiomatic phrases to some
    sentences so about `ratio` of sentences contain a short phrase. It's safe
    for short responses and keeps core content intact.
    """
    if not text:
        return text

    phrases = [
        "Muli bwanji?",
        "Zikomo.",
        "Natotela!",
        "Tikulandira.",
        "Moni!",
        "Mwabala bwino.",
    ]

    # Split into sentences (naive) and determine how many to annotate
    sentences = [s.strip() for s in text.replace("\n", " ").split(".") if s.strip()]
    if not sentences:
        return text

    ratio = random.uniform(ratio_min, ratio_max)
    num_to_tag = max(1, int(len(sentences) * ratio))

    # Choose sentence indices to tag
    indices = set()
    attempts = 0
    while len(indices) < num_to_tag and attempts < 20:
        indices.add(random.randrange(0, len(sentences)))
        attempts += 1

    for i in indices:
        phrase = random.choice(phrases)
        # Append small phrase to the sentence with a separating comma
        sentences[i] = sentences[i] + ", " + phrase

    # Reconstruct text (join with period + space) and preserve trailing punctuation
    final = ". ".join(sentences)
    if text.endswith((".", "!", "?")):
        final = final + text[-1]
    return final
