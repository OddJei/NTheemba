"""Lightweight outbox shim used for local runs/tests.

This module intentionally implements a permissive `create_outbox_row` function
that accepts any arguments and returns a simple dict. It avoids touching any
external systems and is only intended to allow the services to start locally.
"""
from typing import Any


def create_outbox_row(*args: Any, **kwargs: Any) -> dict:
    """Create a no-op outbox record representation.

    Callers may expect an object or DB row; returning a dict avoids attribute
    access errors in typical code paths used during startup.
    """
    return {"status": "stub", "args": args, "kwargs": kwargs}
