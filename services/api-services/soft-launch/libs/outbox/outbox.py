"""Small shared Outbox helper utilities.

Usage:
  from libs.outbox.outbox import create_outbox_row
  await create_outbox_row(db_session, "msme.subscription.payment_succeeded", payload, correlation_id="corr-1", idempotency_key="evt-1")

This helper is intentionally small and DB-agnostic: it issues a parameterized INSERT into
an `outbox_events` table. Services should adapt column names/types to their schema if needed.
"""
from __future__ import annotations
import json
from datetime import datetime
from typing import Optional, Any, Dict
import inspect
from collections.abc import Awaitable

from sqlalchemy import text


async def create_outbox_row(session, event_type: str, payload: Dict[str, Any], *, correlation_id: Optional[str] = None,
                      idempotency_key: Optional[str] = None, send_after: Optional[datetime] = None) -> None:
    """Insert an Outbox row using the provided SQLAlchemy session.

    - `session` should be an AsyncSession or sync Session with an `execute(text(..), params)` method.
    - This function does NOT commit; caller should manage transaction boundaries so Outbox writes
      are made inside the same DB transaction as the authoritative state change.

    Expected table columns (Postgres names/types suggested):
      - id (uuid / serial)
      - event_type (text)
      - payload (jsonb)
      - correlation_id (text)
      - idempotency_key (text)
      - status (text) default 'pending'
      - send_after (timestamp with tz nullable)
      - attempts (int) default 0
      - created_at (timestamp with tz)

    Adjust this helper or use an ORM model in each service if your schema differs.
    """
    now = datetime.utcnow()
    params = {
        "event_type": event_type,
        "payload": json.dumps(payload),
        "correlation_id": correlation_id,
        "idempotency_key": idempotency_key,
        "status": "pending",
        "send_after": send_after,
        "attempts": 0,
        "created_at": now,
    }

    # Postgres-friendly insert; services on other DBs may need to adapt the `payload::jsonb` cast.
    sql = text(
        """
        INSERT INTO outbox_events
          (event_type, payload, correlation_id, idempotency_key, status, send_after, attempts, created_at)
        VALUES
          (:event_type, :payload::jsonb, :correlation_id, :idempotency_key, :status, :send_after, :attempts, :created_at)
        """
    )

    # Support both sync and async SQLAlchemy sessions by calling execute directly.
    res = session.execute(sql, params)
    if inspect.isawaitable(res) or isinstance(res, Awaitable):
        await res


def create_outbox_row_raw(session, raw_sql: str, params: Dict[str, Any]) -> None:
    """Execute a custom raw SQL insert into the Outbox using the provided session.

    Use when you need to adapt to a different schema. This helper only forwards to session.execute.
    """
    session.execute(text(raw_sql), params)
