"""Asyncio compatibility helpers for platform-specific runtimes."""

from __future__ import annotations

import asyncio
import sys


def use_windows_selector_event_loop_policy() -> None:
    """Use an event loop compatible with psycopg async connections on Windows."""

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
