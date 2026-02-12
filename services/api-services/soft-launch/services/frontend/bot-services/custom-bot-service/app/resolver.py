from __future__ import annotations

import time
import asyncio
from typing import Any, Dict, Iterable, List

from .oob_store import OOBStore


NEGATIVE_CACHE_TTL = 60  # seconds

# In-process single-flight locks per blob key. This prevents multiple concurrent
# hydrations for the same blob within the same process. Note: for multi-process
# deployments a distributed lock would be required.
_KEY_LOCKS: dict[str, asyncio.Lock] = {}


async def resolve_required_blobs(
    *,
    store: OOBStore,
    session_id: str,
    required_blobs: Iterable[str],
    ice_client=None,
    event_id: str | None = None,
) -> Dict[str, Any]:
    """Cache-first resolver used by handlers.

    - Reads current OOB and looks for blobs in `oob.meta.hydrated_blobs`.
    - If blobs are missing and `ice_client` is provided, calls `ice_client.hydrate`.
    - Writes returned blobs back into `oob.meta.hydrated_blobs` via CAS.
    - Implements a tiny negative cache inside `oob.meta.negative_cache`.

    Returns a dict mapping requested blob keys to their values (or None).
    """

    req = list(required_blobs or [])
    if not req:
        return {}

    oob, ver = await store.create_default_if_missing(session_id)
    meta = oob.get("meta") or {}
    hydrated = dict(meta.get("hydrated_blobs") or {})
    negative = dict(meta.get("negative_cache") or {})

    now = int(time.time())

    to_request: List[str] = []
    result: Dict[str, Any] = {}

    for key in req:
        # check negative cache
        neg_ts = negative.get(key)
        if neg_ts and (now - int(neg_ts)) < NEGATIVE_CACHE_TTL:
            result[key] = None
            continue

        if key in hydrated:
            result[key] = hydrated.get(key)
        else:
            to_request.append(key)

    if to_request and ice_client is not None:
        # Acquire per-key locks (sorted to avoid deadlocks). Prefer a Redis
        # distributed lock when the OOBStore exposes a Redis client (`_r`). If
        # Redis client is unavailable (tests or in-memory stores), fall back to
        # in-process asyncio Locks.
        locks_acquired = []
        keys = sorted(set(to_request))
        try:
            use_redis = hasattr(store, "_r") and getattr(store, "_r") is not None

            if use_redis:
                # Use redis.asyncio Lock objects
                redis_client = getattr(store, "_r")
                for k in keys:
                    lock_name = f"resolver:lock:{k}"
                    lock = redis_client.lock(lock_name, timeout=10, blocking_timeout=5)
                    # acquire returns True/False
                    try:
                        ok = await lock.acquire()
                    except Exception:
                        ok = False
                    if not ok:
                        # Failed to acquire a distributed lock; proceed to next
                        # key (we'll re-check OOB and avoid double work if possible)
                        continue
                    locks_acquired.append(lock)
            else:
                for k in keys:
                    lock = _KEY_LOCKS.get(k)
                    if lock is None:
                        lock = asyncio.Lock()
                        _KEY_LOCKS[k] = lock
                    await lock.acquire()
                    locks_acquired.append(lock)

            # Re-check OOB after acquiring locks in case another task already
            # hydrated the blobs while we were waiting.
            oob2, ver2 = await store.create_default_if_missing(session_id)
            meta2 = oob2.get("meta") or {}
            hydrated2 = dict(meta2.get("hydrated_blobs") or {})
            negative2 = dict(meta2.get("negative_cache") or {})

            still_needed: List[str] = []
            now2 = int(time.time())
            for k in to_request:
                neg_ts = negative2.get(k)
                if neg_ts and (now2 - int(neg_ts)) < NEGATIVE_CACHE_TTL:
                    result[k] = None
                    continue
                if k in hydrated2:
                    result[k] = hydrated2.get(k)
                else:
                    still_needed.append(k)

            if still_needed:
                try:
                    resp = await ice_client.hydrate(session_id=session_id, required_blobs=still_needed, event_id=event_id)
                except Exception:
                    resp = {}

                # write hydrate results back into OOB.meta.hydrated_blobs (merge)
                def _upd(o: dict[str, Any]) -> dict[str, Any]:
                    o = dict(o)
                    m = dict(o.get("meta") or {})
                    hb = dict(m.get("hydrated_blobs") or {})
                    nc = dict(m.get("negative_cache") or {})

                    for k in still_needed:
                        v = resp.get(k)
                        if v is None:
                            nc[k] = int(time.time())
                            hb.pop(k, None)
                        else:
                            hb[k] = v
                            nc.pop(k, None)

                    m["hydrated_blobs"] = hb
                    m["negative_cache"] = nc
                    o["meta"] = m
                    o["last_node_executed"] = "resolver.hydrate"
                    return o

                try:
                    await store.cas_update(session_id, _upd)
                except Exception:
                    # on CAS failure we still assemble result from resp + previous
                    pass

                # merge resp into result
                for k in still_needed:
                    result[k] = resp.get(k)
            # end if still_needed

        finally:
            # release locks (redis locks have async `release`, in-process are sync)
            for l in locks_acquired:
                try:
                    # redis.asyncio Lock has async release
                    if hasattr(l, "release") and asyncio.iscoroutinefunction(l.release):
                        await l.release()
                    else:
                        # in-process asyncio.Lock.release is a normal function
                        try:
                            l.release()
                        except Exception:
                            pass
                except Exception:
                    pass

    return result
