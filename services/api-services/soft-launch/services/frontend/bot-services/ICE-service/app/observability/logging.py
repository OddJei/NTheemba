"""
Phase 6: Observability - Structured Logging

Centralized logging with structured context for better debuggability.
All logs include event_id, session_id, order_id for correlation.
"""

from __future__ import annotations

import logging
import json
from typing import Any
from datetime import datetime

# Configure structured logging
class StructuredLogFormatter(logging.Formatter):
    """Format logs as JSON for ELK/CloudWatch ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields from record
        if hasattr(record, "__dict__"):
            for key, value in record.__dict__.items():
                if key not in ("name", "msg", "args", "created", "filename", "funcName", "levelname", "levelno", "lineno", "module", "msecs", "message", "pathname", "process", "processName", "relativeCreated", "thread", "threadName", "exc_info", "exc_text", "stack_info"):
                    log_data[key] = value

        return json.dumps(log_data)


def setup_logging(name: str, level: int = logging.INFO) -> logging.Logger:
    """Configure structured logging for a module."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    handler = logging.StreamHandler()
    formatter = StructuredLogFormatter()
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


class LogContext:
    """Helper to log with consistent context."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def info(self, message: str, **context: Any) -> None:
        """Log info with context."""
        self.logger.info(message, extra=context)

    def warning(self, message: str, **context: Any) -> None:
        """Log warning with context."""
        self.logger.warning(message, extra=context)

    def error(self, message: str, **context: Any) -> None:
        """Log error with context."""
        self.logger.error(message, extra=context)

    def exception(self, message: str, exc: Exception, **context: Any) -> None:
        """Log exception with context."""
        context["exception_type"] = type(exc).__name__
        context["exception_message"] = str(exc)
        self.logger.exception(message, extra=context)


# Recommended context fields for all logs:
# - event_id: Unique request identifier (for tracing)
# - session_id: User session identifier
# - order_id: Order identifier (if applicable)
# - user_id: User identifier
# - bot_id: Bot identifier
# - correlation_id: Request tracing ID
# - duration_ms: Operation duration
# - status: Operation status (success, failure, partial)
# - error_code: Error code if applicable
