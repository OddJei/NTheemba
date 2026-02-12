"""Structured logging utilities for ICE service.

Provides correlation ID tracking, structured context, and async-safe logging.
"""

import logging
import contextvars
from typing import Any, Optional, Dict
from datetime import datetime

# Context variables for correlation tracing
_correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default="unknown"
)
_trace_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "trace_id", default="unknown"
)
_span_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "span_id", default="unknown"
)


class CorrelationFilter(logging.Filter):
    """Add correlation context to log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id()
        record.trace_id = get_trace_id()
        record.span_id = get_span_id()
        record.timestamp = datetime.utcnow().isoformat()
        return True


def setup_logging() -> None:
    """Configure structured logging with correlation support."""
    logger = logging.getLogger()
    
    # Add correlation filter to all handlers
    correlation_filter = CorrelationFilter()
    for handler in logger.handlers:
        handler.addFilter(correlation_filter)
    
    # Set format with correlation fields
    formatter = logging.Formatter(
        "%(timestamp)s - %(name)s - %(levelname)s - "
        "[%(correlation_id)s] [%(trace_id)s] [%(span_id)s] - %(message)s"
    )
    for handler in logger.handlers:
        handler.setFormatter(formatter)


def set_correlation_id(correlation_id: str) -> None:
    """Set correlation ID for request tracing."""
    _correlation_id.set(correlation_id)


def get_correlation_id() -> str:
    """Get current correlation ID."""
    return _correlation_id.get()


def set_trace_id(trace_id: str) -> None:
    """Set trace ID (from incoming request)."""
    _trace_id.set(trace_id)


def get_trace_id() -> str:
    """Get current trace ID."""
    return _trace_id.get()


def set_span_id(span_id: str) -> None:
    """Set span ID (unique per operation)."""
    _span_id.set(span_id)


def get_span_id() -> str:
    """Get current span ID."""
    return _span_id.get()


def log_event(
    logger: logging.Logger,
    event_name: str,
    level: int = logging.INFO,
    **context: Any,
) -> None:
    """Log structured event with context.
    
    Usage:
        log_event(
            logger,
            "hydration_started",
            session_id="sess_123",
            bot_type="custom",
            adapter_count=4,
        )
    """
    context_str = " | ".join(f"{k}={v}" for k, v in context.items())
    message = f"{event_name} | {context_str}"
    logger.log(level, message, extra=context)


def log_operation_start(
    logger: logging.Logger,
    operation_name: str,
    **context: Any,
) -> None:
    """Log operation start."""
    log_event(logger, f"{operation_name}.start", logging.INFO, **context)


def log_operation_end(
    logger: logging.Logger,
    operation_name: str,
    duration_ms: float,
    status: str,
    **context: Any,
) -> None:
    """Log operation completion."""
    context["duration_ms"] = duration_ms
    context["status"] = status
    log_event(logger, f"{operation_name}.end", logging.INFO, **context)


def log_error(
    logger: logging.Logger,
    operation_name: str,
    error: Exception,
    **context: Any,
) -> None:
    """Log error with full context."""
    context["error"] = str(error)
    context["error_type"] = type(error).__name__
    log_event(logger, f"{operation_name}.error", logging.ERROR, **context)


class StructuredLogger:
    """Wrapper for structured logging with context."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.context: Dict[str, Any] = {}
    
    def with_context(self, **context: Any) -> "StructuredLogger":
        """Add context that will be included in all subsequent logs."""
        self.context.update(context)
        return self
    
    def info(self, event_name: str, **context: Any) -> None:
        """Log info event."""
        merged_context = {**self.context, **context}
        log_event(self.logger, event_name, logging.INFO, **merged_context)
    
    def warning(self, event_name: str, **context: Any) -> None:
        """Log warning event."""
        merged_context = {**self.context, **context}
        log_event(self.logger, event_name, logging.WARNING, **merged_context)
    
    def error(self, event_name: str, **context: Any) -> None:
        """Log error event."""
        merged_context = {**self.context, **context}
        log_event(self.logger, event_name, logging.ERROR, **merged_context)
    
    def debug(self, event_name: str, **context: Any) -> None:
        """Log debug event."""
        merged_context = {**self.context, **context}
        log_event(self.logger, event_name, logging.DEBUG, **merged_context)


def get_structured_logger(logger: logging.Logger) -> StructuredLogger:
    """Get a structured logger wrapper."""
    return StructuredLogger(logger)
