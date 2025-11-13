from prometheus_client import Counter, Histogram

INGRESS_PROCESSED = Counter("ingress_processed_total", "Number of successfully processed ingress messages")
INGRESS_DUPLICATES = Counter("ingress_duplicates_total", "Number of duplicate ingress messages skipped")
INGRESS_DLQ = Counter("ingress_dlq_total", "Number of messages pushed to DLQ")
INGRESS_LATENCY = Histogram("ingress_processing_seconds", "Histogram of ingress processing latency seconds")


def observe_processed(duration_seconds: float):
    INGRESS_PROCESSED.inc()
    INGRESS_LATENCY.observe(duration_seconds)


def observe_duplicate():
    INGRESS_DUPLICATES.inc()


def observe_dlq():
    INGRESS_DLQ.inc()
