# Phase 12.9 — Simulator and Storage Diagnostics

The developer conversation simulator uses the configured session repository, distributed locks and deduplication store. Redis mode therefore supports restart and duplicate-delivery testing through the same chat UI used in Phase 11.11.

Protected `/dev/storage` routes expose backend health, identity recognition, consent, names, addresses, checkout context and tenant-scoped customer memory. They remain disabled outside development/test environments.
