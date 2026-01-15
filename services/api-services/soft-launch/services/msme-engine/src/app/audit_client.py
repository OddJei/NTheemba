"""
Audit client for emitting audit events to the centralized audit service.
"""
import asyncio
import logging
import os
import traceback
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import httpx


logger = logging.getLogger("audit_client")


def get_audit_service_url() -> str:
    return os.getenv("AUDIT_SERVICE_URL", "http://127.0.0.1:8290")


def get_audit_timeout() -> float:
    try:
        return float(os.getenv("AUDIT_TIMEOUT_SECONDS", "3.0"))
    except ValueError:
        return 3.0


def audit_emit_enabled() -> bool:
    v = os.getenv("AUDIT_EMIT_ENABLED", "true").strip().lower()
    return v not in {"0", "false", "no", "off"}


def _jsonable(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    return str(value)


async def emit_audit(
    service: str,
    event_type: str,
    payload: Dict[str, Any],
    actor_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    severity: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    if not audit_emit_enabled():
        return False

    audit_url = get_audit_service_url().rstrip("/")
    timeout = get_audit_timeout()

    event = {
        "service": service,
        "event_type": event_type,
        "payload": _jsonable(payload),
    }

    if actor_id:
        event["actor_id"] = actor_id
    if entity_type:
        event["entity_type"] = entity_type
    if entity_id:
        event["entity_id"] = entity_id
    if severity:
        event["severity"] = severity
    if metadata:
        event["metadata"] = _jsonable(metadata)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(f"{audit_url}/audit/log", json=event)
            if r.status_code in (200, 201):
                return True
            logger.warning("audit_emit_failed", extra={"status": r.status_code, "service": service, "event_type": event_type})
    except httpx.RequestError as e:
        logger.debug("audit_service_unreachable", extra={"service": service, "event_type": event_type, "error": str(e)})
    except Exception as e:
        logger.warning("audit_emit_exception", extra={"service": service, "event_type": event_type, "error": str(e)})

    return False


def emit_audit_sync(
    service: str,
    event_type: str,
    payload: Dict[str, Any],
    actor_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    severity: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    try:
        if not audit_emit_enabled():
            return False

        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(
                emit_audit(
                    service=service,
                    event_type=event_type,
                    payload=payload,
                    actor_id=actor_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    severity=severity,
                    metadata=metadata,
                )
            )
            return True
        else:
            return loop.run_until_complete(
                emit_audit(
                    service=service,
                    event_type=event_type,
                    payload=payload,
                    actor_id=actor_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    severity=severity,
                    metadata=metadata,
                )
            )
    except Exception as e:
        logger.warning("audit_emit_sync_failed", extra={"error": str(e)})
        return False


# --- Log forwarding handler ---
def audit_forward_logs_enabled() -> bool:
    v = os.getenv("AUDIT_FORWARD_LOGS_ENABLED", "true").strip().lower()
    return v not in {"0", "false", "no", "off"}


def get_audit_forward_logs_level() -> int:
    raw = os.getenv("AUDIT_FORWARD_LOGS_LEVEL", "WARNING").strip().upper()
    try:
        return int(raw)
    except ValueError:
        return int(getattr(logging, raw, logging.WARNING))


def get_audit_forward_logs_exclude_prefixes() -> tuple[str, ...]:
    raw = os.getenv("AUDIT_FORWARD_LOGS_EXCLUDE", "audit_client,httpx,httpcore,asyncio")
    parts = [p.strip() for p in raw.split(",")]
    return tuple(p for p in parts if p)


_STANDARD_LOG_RECORD_ATTRS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
}


class AuditLogForwardingHandler(logging.Handler):
    def __init__(self, *, service: str, level: int, exclude_prefixes: tuple[str, ...]) -> None:
        super().__init__(level=level)
        self._service = service
        self._exclude_prefixes = exclude_prefixes

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if not audit_emit_enabled() or not audit_forward_logs_enabled():
                return

            if record.name.startswith(self._exclude_prefixes):
                return

            payload: dict = {
                "message": record.getMessage(),
                "logger": record.name,
                "level": record.levelname,
                "pathname": record.pathname,
                "lineno": record.lineno,
                "func": record.funcName,
            }

            if record.exc_info:
                payload["exception"] = "".join(traceback.format_exception(*record.exc_info))

            extras = {k: v for k, v in record.__dict__.items() if k not in _STANDARD_LOG_RECORD_ATTRS and not k.startswith("_")}
            if extras:
                payload["extra"] = _jsonable(extras)

            severity = record.levelname.lower()
            emit_audit_sync(service=self._service, event_type="python_log", payload=payload, severity=severity)
        except Exception:
            return


def install_audit_log_forwarding(*, service: str) -> None:
    if not audit_forward_logs_enabled():
        return

    root = logging.getLogger()
    for h in root.handlers:
        if isinstance(h, AuditLogForwardingHandler) and getattr(h, "_service", None) == service:
            return

    handler = AuditLogForwardingHandler(service=service, level=get_audit_forward_logs_level(), exclude_prefixes=get_audit_forward_logs_exclude_prefixes())
    root.addHandler(handler)
