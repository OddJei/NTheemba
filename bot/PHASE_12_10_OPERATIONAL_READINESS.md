# Phase 12.10 — Persistence Operational Readiness

Operational deliverables include:

- `docker-compose.phase12.yml`;
- PostgreSQL migration runner;
- customer-memory retention cleanup;
- storage connectivity self-check;
- readiness endpoint integration;
- environment validation;
- memory fallback for dependency-free tests;
- deployment and restart test instructions.

Before production, run the complete Python quality gate, migrations against a disposable database, storage self-check, restart continuity test, concurrent-message lock test and tenant-isolation test using a non-superuser PostgreSQL role.
