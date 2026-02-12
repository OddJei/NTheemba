"""Idempotency helpers for ICE workflows."""

from typing import NewType

IdempotencyKey = NewType("IdempotencyKey", str)
