"""
Phase 6: Observability - Metrics (Prometheus)

Metrics for monitoring ICE service health and performance.
Includes latency histograms, error counters, cache hit rates.
"""

from __future__ import annotations

import time
from typing import Callable, Any
from functools import wraps

try:
    from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Create dummy metrics for when prometheus is not installed
    class DummyMetric:
        def __call__(self, *args, **kwargs):
            pass
        def inc(self, amount=1, labelnames=None):
            pass
        def observe(self, amount):
            pass
        def set(self, amount):
            pass
        def labels(self, **kwargs):
            return self

    Counter = DummyMetric
    Histogram = DummyMetric
    Gauge = DummyMetric


# Create registry
if PROMETHEUS_AVAILABLE:
    registry = CollectorRegistry()
else:
    registry = None


# ============================================================================
# API Endpoint Metrics
# ============================================================================

hydrate_latency = Histogram(
    "ice_hydrate_latency_seconds",
    "Latency of POST /api/v1/hydrate/session endpoint",
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0),
    registry=registry if PROMETHEUS_AVAILABLE else None,
)

hydrate_requests = Counter(
    "ice_hydrate_requests_total",
    "Total requests to POST /api/v1/hydrate/session",
    ["status"],  # success, validation_error, server_error
    registry=registry if PROMETHEUS_AVAILABLE else None,
)

reserve_latency = Histogram(
    "ice_reserve_latency_seconds",
    "Latency of POST /api/v1/reserve endpoint",
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0),
    registry=registry if PROMETHEUS_AVAILABLE else None,
)

reserve_requests = Counter(
    "ice_reserve_requests_total",
    "Total requests to POST /api/v1/reserve",
    ["status"],
    registry=registry if PROMETHEUS_AVAILABLE else None,
)

confirm_latency = Histogram(
    "ice_confirm_latency_seconds",
    "Latency of POST /api/v1/confirm endpoint",
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0),
    registry=registry if PROMETHEUS_AVAILABLE else None,
)

confirm_requests = Counter(
    "ice_confirm_requests_total",
    "Total requests to POST /api/v1/confirm",
    ["status"],
    registry=registry if PROMETHEUS_AVAILABLE else None,
)

payment_status_latency = Histogram(
    "ice_payment_status_latency_seconds",
    "Latency of GET /api/v1/orders/{order_id}/payment_status",
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0),
    registry=registry if PROMETHEUS_AVAILABLE else None,
)

cancel_latency = Histogram(
    "ice_cancel_latency_seconds",
    "Latency of POST /api/v1/orders/{order_id}/cancel",
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0),
    registry=registry if PROMETHEUS_AVAILABLE else None,
)


# ============================================================================
# Workflow Metrics
# ============================================================================

hydration_latency = Histogram(
    "ice_hydration_workflow_seconds",
    "Latency of hydration workflow",
    ["component"],  # session_adapter, order_draft_adapter, bot_meta_adapter
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0),
    registry=registry if PROMETHEUS_AVAILABLE else None,
)

hydration_errors = Counter(
    "ice_hydration_errors_total",
    "Total hydration errors",
    ["component", "error_type"],
    registry=registry if PROMETHEUS_AVAILABLE else None,
)

reservation_latency = Histogram(
    "ice_reservation_workflow_seconds",
    "Latency of reservation workflow",
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0),
    registry=registry if PROMETHEUS_AVAILABLE else None,
)

confirmation_latency = Histogram(
    "ice_confirmation_workflow_seconds",
    "Latency of confirmation workflow",
    buckets=(0.05, 0.1, 0.5, 1.0, 2.0, 5.0),
    registry=registry if PROMETHEUS_AVAILABLE else None,
)

workflow_errors = Counter(
    "ice_workflow_errors_total",
    "Total workflow errors",
    ["workflow_type", "error_code"],  # hydration|reservation|confirmation, ICE_HYDRATION_FAILED, etc
    registry=registry if PROMETHEUS_AVAILABLE else None,
)


# ============================================================================
# Cache Metrics
# ============================================================================

cache_hits = Counter(
    "ice_cache_hits_total",
    "Total cache hits",
    ["cache_type"],  # session, order_draft, hydrated_session
    registry=registry if PROMETHEUS_AVAILABLE else None,
)

cache_misses = Counter(
    "ice_cache_misses_total",
    "Total cache misses",
    ["cache_type"],
    registry=registry if PROMETHEUS_AVAILABLE else None,
)

cache_size = Gauge(
    "ice_cache_size_bytes",
    "Estimated cache size in bytes",
    ["cache_type"],
    registry=registry if PROMETHEUS_AVAILABLE else None,
)


# ============================================================================
# Repository Metrics
# ============================================================================

db_query_latency = Histogram(
    "ice_db_query_seconds",
    "Database query latency",
    ["query_type"],  # select, insert, update, delete
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5),
    registry=registry if PROMETHEUS_AVAILABLE else None,
)

db_errors = Counter(
    "ice_db_errors_total",
    "Total database errors",
    ["error_type"],  # connection, timeout, constraint_violation
    registry=registry if PROMETHEUS_AVAILABLE else None,
)

db_connection_pool_size = Gauge(
    "ice_db_connections_active",
    "Active database connections",
    registry=registry if PROMETHEUS_AVAILABLE else None,
)


# ============================================================================
# Stream Metrics (Workers)
# ============================================================================

stream_messages_processed = Counter(
    "ice_stream_messages_processed_total",
    "Total stream messages processed",
    ["stream_name", "status"],  # success, error, dlq
    registry=registry if PROMETHEUS_AVAILABLE else None,
)

stream_processing_latency = Histogram(
    "ice_stream_processing_seconds",
    "Stream message processing latency",
    ["stream_name"],  # ice:preload, oob:audit
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0),
    registry=registry if PROMETHEUS_AVAILABLE else None,
)

stream_lag = Gauge(
    "ice_stream_lag_messages",
    "Stream consumer lag (pending messages)",
    ["stream_name", "consumer_group"],
    registry=registry if PROMETHEUS_AVAILABLE else None,
)

dlq_messages = Counter(
    "ice_dlq_messages_total",
    "Total messages sent to DLQ",
    ["stream_name"],
    registry=registry if PROMETHEUS_AVAILABLE else None,
)


# ============================================================================
# Business Metrics
# ============================================================================

orders_created = Counter(
    "ice_orders_created_total",
    "Total orders created",
    ["bot_type"],  # default, custom
    registry=registry if PROMETHEUS_AVAILABLE else None,
)

orders_confirmed = Counter(
    "ice_orders_confirmed_total",
    "Total orders confirmed",
    registry=registry if PROMETHEUS_AVAILABLE else None,
)

orders_cancelled = Counter(
    "ice_orders_cancelled_total",
    "Total orders cancelled",
    ["reason"],  # user_cancelled, payment_failed, timeout
    registry=registry if PROMETHEUS_AVAILABLE else None,
)

payment_methods_used = Counter(
    "ice_payments_total",
    "Total payments processed",
    ["payment_method", "status"],  # mobile_money|card, success|failed
    registry=registry if PROMETHEUS_AVAILABLE else None,
)

cart_value = Histogram(
    "ice_cart_value_minor_units",
    "Cart total value (in minor currency units)",
    buckets=(1000, 5000, 10000, 50000, 100000, 500000),
    registry=registry if PROMETHEUS_AVAILABLE else None,
)


# ============================================================================
# Decorator for automatic metrics
# ============================================================================

def track_latency(metric_name: str | Histogram):
    """Decorator to track function latency."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            start = time.time()
            try:
                return await func(*args, **kwargs)
            finally:
                duration = time.time() - start
                if isinstance(metric_name, str):
                    # Look up metric by name (not recommended, use Histogram directly)
                    pass
                else:
                    metric_name.observe(duration)

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            start = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.time() - start
                if not isinstance(metric_name, str):
                    metric_name.observe(duration)

        # Return async or sync wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


import asyncio
