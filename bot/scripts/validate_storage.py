"""Validate configured Redis/PostgreSQL storage connectivity and readiness."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ntheemba.config import get_settings
from ntheemba.infrastructure.asyncio_compat import use_windows_selector_event_loop_policy
from ntheemba.infrastructure.storage import build_storage_runtime


async def validate() -> None:
    runtime = build_storage_runtime(get_settings())
    await runtime.open()
    try:
        snapshot = await runtime.snapshot()
        if not (snapshot.opened and snapshot.redis_ready and snapshot.postgres_ready):
            raise SystemExit(f"Storage self-check failed: {snapshot}")
        print("Storage self-check passed")
        print(snapshot)
    finally:
        await runtime.close()


if __name__ == "__main__":
    use_windows_selector_event_loop_policy()
    asyncio.run(validate())
