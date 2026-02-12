"""Metrics collection and emission for ICE service.

Tracks:
- Workflow latency (hydrate, reserve, confirm, payment_status, cancel)
- Operation counts and success rates
- Cache hit rates
- Error rates by error code
- Adapter call latency
"""

import time
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Metric types."""
    HISTOGRAM = "histogram"
    COUNTER = "counter"
    GAUGE = "gauge"


@dataclass
class MetricEvent:
    """Structured metric event."""
    name: str
    value: float
    metric_type: MetricType
    labels: Dict[str, str]
    timestamp: float


class MetricsCollector:
    """Collect and emit metrics."""
    
    def __init__(self):
        self.events: list[MetricEvent] = []
    
    def record_histogram(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record histogram metric (latency, duration)."""
        self.events.append(
            MetricEvent(
                name=name,
                value=value,
                metric_type=MetricType.HISTOGRAM,
                labels=labels or {},
                timestamp=time.time(),
            )
        )
        logger.info(
            f"metric.histogram",
            extra={
                "name": name,
                "value": value,
                "labels": labels or {},
            },
        )
    
    def record_counter(
        self,
        name: str,
        value: int = 1,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record counter metric (requests, errors)."""
        self.events.append(
            MetricEvent(
                name=name,
                value=float(value),
                metric_type=MetricType.COUNTER,
                labels=labels or {},
                timestamp=time.time(),
            )
        )
        logger.info(
            f"metric.counter",
            extra={
                "name": name,
                "value": value,
                "labels": labels or {},
            },
        )
    
    def record_gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record gauge metric (queue size, memory usage)."""
        self.events.append(
            MetricEvent(
                name=name,
                value=value,
                metric_type=MetricType.GAUGE,
                labels=labels or {},
                timestamp=time.time(),
            )
        )


class TimerContext:
    """Context manager for measuring operation latency."""
    
    def __init__(self, collector: MetricsCollector, name: str, labels: Optional[Dict[str, str]] = None):
        self.collector = collector
        self.name = name
        self.labels = labels or {}
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed_ms = (time.time() - self.start_time) * 1000
        self.collector.record_histogram(
            self.name,
            elapsed_ms,
            labels=self.labels,
        )
    
    async def __aenter__(self):
        self.start_time = time.time()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        elapsed_ms = (time.time() - self.start_time) * 1000
        self.collector.record_histogram(
            self.name,
            elapsed_ms,
            labels=self.labels,
        )


# Global metrics collector instance
_metrics = MetricsCollector()


def get_metrics() -> MetricsCollector:
    """Get global metrics collector."""
    return _metrics


def timer(name: str, labels: Optional[Dict[str, str]] = None) -> TimerContext:
    """Create a timer context for measuring operation latency.
    
    Usage (sync):
        with timer("hydrate.latency", labels={"bot_type": "custom"}):
            await hydrate_session(...)
    
    Usage (async):
        async with timer("hydrate.latency", labels={"bot_type": "custom"}):
            await hydrate_session(...)
    """
    return TimerContext(_metrics, name, labels)


def record_hydrate_latency(latency_ms: float, bot_type: str, status: str) -> None:
    """Record hydration latency."""
    _metrics.record_histogram(
        "ice.hydrate.latency_ms",
        latency_ms,
        labels={"bot_type": bot_type, "status": status},
    )
    _metrics.record_counter(
        "ice.hydrate.requests",
        labels={"bot_type": bot_type, "status": status},
    )


def record_reserve_latency(latency_ms: float, status: str, error_code: Optional[str] = None) -> None:
    """Record reserve latency."""
    _metrics.record_histogram(
        "ice.reserve.latency_ms",
        latency_ms,
        labels={"status": status, "error_code": error_code or "none"},
    )
    _metrics.record_counter(
        "ice.reserve.requests",
        labels={"status": status},
    )


def record_confirm_latency(latency_ms: float, status: str, error_code: Optional[str] = None) -> None:
    """Record confirm latency."""
    _metrics.record_histogram(
        "ice.confirm.latency_ms",
        latency_ms,
        labels={"status": status, "error_code": error_code or "none"},
    )
    _metrics.record_counter(
        "ice.confirm.requests",
        labels={"status": status},
    )


def record_adapter_call(adapter_name: str, latency_ms: float, status: str) -> None:
    """Record adapter call latency."""
    _metrics.record_histogram(
        "ice.adapter.latency_ms",
        latency_ms,
        labels={"adapter": adapter_name, "status": status},
    )


def record_cache_hit(cache_key_pattern: str, hit: bool) -> None:
    """Record cache hit/miss."""
    _metrics.record_counter(
        "ice.cache.requests",
        labels={"pattern": cache_key_pattern, "hit": "yes" if hit else "no"},
    )


def record_error(error_code: str, operation: str) -> None:
    """Record error occurrence."""
    _metrics.record_counter(
        "ice.errors",
        labels={"error_code": error_code, "operation": operation},
    )


def record_idempotency_hit(operation: str) -> None:
    """Record idempotency cache hit."""
    _metrics.record_counter(
        "ice.idempotency.hits",
        labels={"operation": operation},
    )


def record_cas_conflict() -> None:
    """Record optimistic CAS conflict."""
    _metrics.record_counter("ice.cas.conflicts")


def record_payment_status_latency(latency_ms: float, payment_status: str) -> None:
    """Record payment status fetch latency."""
    _metrics.record_histogram(
        "ice.payment_status.latency_ms",
        latency_ms,
        labels={"payment_status": payment_status},
    )


def get_metrics_summary() -> Dict[str, Any]:
    """Get summary of collected metrics.
    
    Returns counts and aggregate statistics.
    """
    metrics = _metrics
    
    return {
        "total_events": len(metrics.events),
        "event_types": {
            "histogram": sum(1 for e in metrics.events if e.metric_type == MetricType.HISTOGRAM),
            "counter": sum(1 for e in metrics.events if e.metric_type == MetricType.COUNTER),
            "gauge": sum(1 for e in metrics.events if e.metric_type == MetricType.GAUGE),
        },
        "recent_events": [
            {
                "name": e.name,
                "value": e.value,
                "type": e.metric_type.value,
                "labels": e.labels,
            }
            for e in metrics.events[-20:]  # Last 20 events
        ],
    }
