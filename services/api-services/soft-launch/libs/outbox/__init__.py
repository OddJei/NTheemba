"""Minimal outbox shim for local development.

This provides a lightweight `create_outbox_row` function so services that
import `libs.outbox.outbox` can run without the full implementation.
"""

from .outbox import create_outbox_row
