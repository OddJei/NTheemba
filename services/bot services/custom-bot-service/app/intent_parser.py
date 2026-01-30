from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Intent:
    id: str
    slots: dict[str, Any]


CONFIRM_ORDER_PHRASE = os.getenv("CUSTOM_BOT_CONFIRM_ORDER_PHRASE", "CONFIRM ORDER")
CONFIRM_PAYMENT_PHRASE = os.getenv("CUSTOM_BOT_CONFIRM_PAYMENT_PHRASE", "CONFIRM PAYMENT")


def _normalize_text(text: str) -> str:
    return " ".join((text or "").strip().split())


def parse_intents(raw_text: str) -> list[Intent]:
    """Very small deterministic intent parser.

    This is Phase-E scaffolding so the service can do something useful
    before Phase C (intent-service) is wired.

    Rules:
    - strict confirm phrases for confirm intents
    - otherwise try to parse one or more 'add_item' intents from patterns like '2 apples'
    - otherwise return 'help'
    """
    text = _normalize_text(raw_text)
    if not text:
        return [Intent(id="help", slots={})]

    if text.upper() == CONFIRM_ORDER_PHRASE.upper():
        return [Intent(id="confirm_order", slots={})]

    if text.upper() == CONFIRM_PAYMENT_PHRASE.upper():
        return [Intent(id="confirm_payment", slots={})]

    intents: list[Intent] = []

    # Split into chunks so "2 apples and 3 oranges" becomes two intents.
    chunks = re.split(r"\s+(?:and|&)\s+|,", text, flags=re.IGNORECASE)
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        m = re.match(r"^(?P<qty>\d+)\s+(?P<name>[A-Za-z][A-Za-z0-9\-\s]{1,60})$", chunk)
        if not m:
            continue
        qty = int(m.group("qty"))
        name = _normalize_text(m.group("name"))
        if qty <= 0:
            continue
        intents.append(Intent(id="add_item", slots={"quantity": qty, "product_name": name}))

    if intents:
        return intents

    return [Intent(id="help", slots={})]
