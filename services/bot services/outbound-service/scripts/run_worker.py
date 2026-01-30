from __future__ import annotations

import asyncio
import signal
import sys
import pathlib

# Make script runnable directly by adding service root to sys.path
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.workers.queue_listener import start_listener
from app.core.config import get_settings
from app.core.redis import get_redis


async def _main():
    settings = get_settings()
    redis_client = get_redis(settings)
    task = asyncio.create_task(start_listener(redis_client=redis_client, settings=settings))

    loop = asyncio.get_running_loop()

    stop = asyncio.Future()

    def _on_sig(signum, frame=None):
        if not stop.done():
            stop.set_result(True)

    for s in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(s, _on_sig, s)
        except NotImplementedError:
            # Windows loop.add_signal_handler may not be available in some envs
            pass

    await stop
    task.cancel()
    try:
        await task
    except Exception:
        pass


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        sys.exit(0)
