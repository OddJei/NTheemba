from prometheus_client import Counter, Histogram

OUTBOUND_PROCESSED = Counter("outbound_processed_total", "Number of outbound messages processed")
OUTBOUND_SENT = Counter("outbound_sent_total", "Number of outbound sends attempted", ["provider", "result"])  # result=ok|failed
OUTBOUND_DUPLICATES = Counter("outbound_duplicates_total", "Number of duplicate event_id skipped")
OUTBOUND_DLQ = Counter("outbound_dlq_total", "Number of messages pushed to outbound DLQ", ["provider"])
OUTBOUND_LATENCY = Histogram("outbound_processing_seconds", "Outbound processing latency seconds", ["provider"])


def observe_processed(provider: str, duration_seconds: float):
    OUTBOUND_PROCESSED.inc()
    OUTBOUND_LATENCY.labels(provider=provider).observe(duration_seconds)


def observe_send(provider: str, result: str):
    OUTBOUND_SENT.labels(provider=provider, result=result).inc()


def observe_duplicate():
    OUTBOUND_DUPLICATES.inc()


def observe_dlq(provider: str):
    OUTBOUND_DLQ.labels(provider=provider).inc()
