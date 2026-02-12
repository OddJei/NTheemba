from __future__ import annotations

import json
import os
import time
from typing import Any

from redis.asyncio import Redis


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value.strip() if value else default


def _pretty(value: Any) -> str:
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("{") or text.startswith("["):
            try:
                return json.dumps(json.loads(text), indent=2, ensure_ascii=False)
            except Exception:
                return value
        return value
    try:
        return json.dumps(value, indent=2, ensure_ascii=False, default=str)
    except Exception:
        return str(value)


async def main() -> None:
    redis_url = _env("REDIS_URL", "redis://localhost:6379/0")
    stream = _env("STREAM", _env("INTENT_RESULTS_STREAM", "intent:results"))

    block_ms = int(_env("BLOCK_MS", "5000"))
    count = int(_env("COUNT", "10"))

    # Tail from "now" by default; set START_ID=0-0 to replay.
    start_id = _env("START_ID", "$")

    redis = Redis.from_url(redis_url, decode_responses=True)
    last_id = start_id

    print(f"tailing stream={stream} start_id={start_id} block_ms={block_ms} count={count}")

    try:
        while True:
            resp = await redis.xread({stream: last_id}, block=block_ms, count=count)
            if not resp:
                continue

            for _, messages in resp:
                for msg_id, fields in messages:
                    last_id = msg_id
                    print("\n---")
                    print(f"id={msg_id}")
                    for k, v in fields.items():
                        if k == "payload":
                            print(f"{k}={_pretty(v)}")
                        else:
                            print(f"{k}={v}")

            time.sleep(0.01)
    finally:
        await redis.aclose()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
