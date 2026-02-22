"""Local Outbox helper for cart service.

Copied from the shared helper so `cart` can import a local helper
(`src.app.helpers.outbox.outbox`) instead of requiring `libs.outbox` on
PYTHONPATH at startup.
"""
from __future__ import annotations
import json
from datetime import datetime
import uuid as _uuid
from typing import Optional, Any, Dict
import inspect
from collections.abc import Awaitable

import logging
from sqlalchemy import text

logger = logging.getLogger("libs.outbox.outbox")


DEFAULT_OUTBOX_TABLE = "public.outbox"


async def create_outbox_row(
    session,
    topic_or_event_type: str,
    payload: Dict[str, Any],
    *,
  id: Optional[str] = None,
    destination: Optional[str] = None,
    correlation_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    send_after: Optional[datetime] = None,
    producer: Optional[str] = None,
    headers: Optional[Dict[str, Any]] = None,
    table: str = DEFAULT_OUTBOX_TABLE,
) -> None:
    now = datetime.utcnow()

    if not id:
      id = str(_uuid.uuid4())

    payload_json = json.dumps(payload) if payload is not None else None
    headers_json = json.dumps(headers) if headers is not None else None

    params = {
      "id": id,
      "topic": topic_or_event_type,
      "destination": destination,
      "payload": payload_json,
      "headers": headers_json,
      "producer": producer,
      "correlation_id": correlation_id,
      "dedupe_key": idempotency_key,
      "status": "pending",
      "attempts": 0,
      "last_error": None,
      "scheduled_at": send_after,
      "priority": 0,
      "created_at": now,
      "updated_at": now,
    }

    dialect_name = ""
    try:
      bind = None
      if hasattr(session, "bind") and session.bind is not None:
        bind = session.bind
      else:
        try:
          bind = session.get_bind()
        except Exception:
          bind = None
      if bind is not None and hasattr(bind, "dialect"):
        dialect_name = getattr(bind.dialect, "name", "") or ""
    except Exception:
      dialect_name = ""

    target_table = table

    sql = text(
      f"""
      INSERT INTO {target_table}
        (id, topic, destination, payload, headers, producer, correlation_id, dedupe_key, status, attempts, last_error, scheduled_at, priority, created_at, updated_at)
      VALUES
        (:id, :topic, :destination, :payload, :headers, :producer, :correlation_id, :dedupe_key, :status, :attempts, :last_error, :scheduled_at, :priority, :created_at, :updated_at)
      """
    )

    try:
      logger.info("outbox_insert_attempt", extra={"target_table": target_table, "topic": params.get("topic"), "id": params.get("id"), "dialect": dialect_name})
      res = session.execute(sql, params)
      if inspect.isawaitable(res) or isinstance(res, Awaitable):
        await res
      logger.info("outbox_inserted", extra={"target_table": target_table, "topic": params.get("topic"), "id": params.get("id")})
      try:
        print(f"OUTBOX-INSERTED target={target_table} id={params.get('id')} topic={params.get('topic')}")
      except Exception:
        pass
      return params.get("id")
    except Exception as exc_primary:
      logger.exception("outbox_insert_failed", extra={"target_table": target_table, "topic": params.get("topic"), "id": params.get("id"), "error": str(exc_primary)})
      try:
        print(f"OUTBOX-INSERT-FAILED primary target={target_table} id={params.get('id')} error={exc_primary}")
      except Exception:
        pass
      last_exc = exc_primary
      try:
        if "." in target_table:
          schema_name = target_table.split('.', 1)[0]
          alt_table = f"{schema_name}.outbox"
        else:
          alt_table = "outbox"
          alt_sql = text(
            f"""
            INSERT INTO {alt_table}
              (id, topic, destination, payload, headers, producer, correlation_id, dedupe_key, status, attempts, last_error, scheduled_at, priority, created_at, updated_at)
            VALUES
              (:id, :topic, :destination, :payload, :headers, :producer, :correlation_id, :dedupe_key, :status, :attempts, :last_error, :scheduled_at, :priority, :created_at, :updated_at)
            """
          )
        logger.debug("outbox_fallback_try", extra={"fallback": alt_table, "id": params.get("id")})
        res2 = session.execute(alt_sql, params)
        if inspect.isawaitable(res2) or isinstance(res2, Awaitable):
          await res2
        logger.info("outbox_fallback_inserted", extra={"fallback": alt_table, "id": params.get("id")})
        try:
          print(f"OUTBOX-FALLBACK-INSERTED fallback={alt_table} id={params.get('id')}")
        except Exception:
          pass
        return params.get("id")
      except Exception as exc_alt:
        logger.exception("outbox_fallback_failed", extra={"fallback": alt_table, "id": params.get("id"), "error": str(exc_alt)})
        try:
          print(f"OUTBOX-FALLBACK-FAILED fallback={alt_table} id={params.get('id')} error={exc_alt}")
        except Exception:
          pass
        last_exc = exc_alt
        try:
          if "." in target_table:
            schema_name = target_table.split('.', 1)[0]
            legacy_table = f"{schema_name}.outbox_events"
          else:
            legacy_table = "outbox_events"
            legacy_sql = text(
              f"""
              INSERT INTO {legacy_table} (id, event_type, payload, target, status, attempts, scheduled_at, created_at)
              VALUES (:id, :topic, :payload, :destination, :status, :attempts, :scheduled_at, :created_at)
              """
            )
          logger.debug("outbox_legacy_fallback_try", extra={"fallback": legacy_table, "id": params.get("id")})
          res3 = session.execute(legacy_sql, params)
          if inspect.isawaitable(res3) or isinstance(res3, Awaitable):
            await res3
          logger.info("outbox_legacy_inserted", extra={"fallback": legacy_table, "id": params.get("id")})
          try:
            print(f"OUTBOX-LEGACY-INSERTED fallback={legacy_table} id={params.get('id')}")
          except Exception:
            pass
          return params.get("id")
        except Exception as exc_legacy:
          logger.exception("outbox_legacy_failed", extra={"fallback": legacy_table, "id": params.get("id"), "error": str(exc_legacy)})
          try:
            print(f"OUTBOX-LEGACY-FAILED fallback={legacy_table} id={params.get('id')} error={exc_legacy}")
          except Exception:
            pass
          raise last_exc


def create_outbox_row_raw(session, raw_sql: str, params: Dict[str, Any]) -> None:
    session.execute(text(raw_sql), params)
