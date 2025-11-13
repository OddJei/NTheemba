from typing import List, Any
from hashlib import sha256
import json
from datetime import datetime

from ..core.config import get_settings


DEFAULT_TTL = 300


async def build_attachment_pack(redis, attachments: List[Any], session_id: str, settings=None):
    """Build an attachment pack suitable for sending as context to intent resolver.

    This function currently normalizes attachments and stores small metadata in Redis
    so downstream services can fetch blobs by key. It returns a list of attachment
    descriptors (id, type, url_or_placeholder).
    """
    settings = settings or get_settings()
    pack = []
    now = datetime.utcnow().isoformat() + "Z"
    for att in attachments or []:
        # simple hash-based id for attachment caching
        raw = json.dumps(att, sort_keys=True, default=str)
        aid = sha256(raw.encode()).hexdigest()[:16]
        key = f"attachment:{session_id}:{aid}"
        # store small metadata so other services can fetch if needed
        try:
            await redis.hset(key, mapping={"meta": raw, "created_at": now})
            await redis.expire(key, DEFAULT_TTL)
        except Exception:
            # best-effort: if redis unavailable, continue and include raw payload
            pass

        pack.append({"id": aid, "meta": att})

    return pack
