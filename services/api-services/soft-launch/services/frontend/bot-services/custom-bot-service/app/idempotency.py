from __future__ import annotations

import os
from typing import Optional

LOCK_TTL = int(os.getenv("CUSTOM_BOT_IDEMP_LOCK_TTL", "30"))
DONE_TTL = int(os.getenv("CUSTOM_BOT_IDEMP_TTL", "86400"))
CONSUMER_NAME = os.getenv("CUSTOM_BOT_CONSUMER_NAME", "custom-bot-1")


def done_key(event_id: str) -> str:
    return f"idempotency:custombot:{event_id}:done"


def lock_key(event_id: str) -> str:
    return f"idempotency:custombot:{event_id}:lock"


async def is_done(r, event_id: str) -> bool:
    k = done_key(event_id)
    v = await r.get(k)
    return bool(v)


async def claim_lock(r, event_id: str, lock_ttl: Optional[int] = None) -> bool:
    k = lock_key(event_id)
    ttl = lock_ttl or LOCK_TTL
    # SET NX EX
    return await r.set(k, CONSUMER_NAME, nx=True, ex=ttl)


async def set_done(r, event_id: str, ttl: Optional[int] = None) -> None:
    k = done_key(event_id)
    t = ttl or DONE_TTL
    await r.set(k, "1", ex=t)
