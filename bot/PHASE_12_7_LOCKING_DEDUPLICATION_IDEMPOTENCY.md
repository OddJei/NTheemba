# Phase 12.7 — Distributed Locking, Deduplication and Idempotency

Redis conversation locks use owner tokens, TTL renewal and ownership-safe Lua release. Ntheemba detects acquisition timeouts and lock loss.

Message IDs are claimed atomically with TTL so gateway retries are processed once.

The idempotency store supports pending, completed and failed records protected by owner tokens. It is ready for live TradeFlow, gateway and other external-action adapters.
