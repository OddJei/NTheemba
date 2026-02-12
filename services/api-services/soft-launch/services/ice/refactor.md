ICE Service Refactor Checklist
===============================

Purpose
-------
Migrate ICE authoritative publishes from Redis streams to an Outbox-first pattern, forward MSME JWTs for downstream calls, and align caching TTLs.

Checklist
---------
- [ ] 1) Replace direct Redis stream publishes with DB Outbox writes
  - Write `OutboxEvent` rows for authoritative events (hydrate/reserve/confirm).

- [ ] 2) Forward MSME JWTs for S2S calls
  - Ensure ICE forwards the `Authorization: Bearer <msme-jwt>` header when calling downstream.

- [ ] 3) Align business cache TTL to 24h
  - Update Redis TTLs and document the policy.

- [ ] 4) Maintain single-flight locks for hot paths
  - Keep existing Redis lock patterns for hydrate/reserve/confirm.

Clarifying questions
--------------------
1) Are there any existing consumers that rely on the Redis stream semantics (ordering/streams groups)? If so, we need a migration plan.
2) Which claim in MSME JWT contains caller identity to forward for attribution?

