This folder contains event bus subscribers (Redis/Kafka) for high-throughput ingestion.

Add subscribers like `subscriber_redis.py` or `subscriber_kafka.py` that forward messages into the `services.audit_service` batched writer.
