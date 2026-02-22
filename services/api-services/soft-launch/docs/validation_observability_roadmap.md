Validation & Observability Roadmap

Phase 0 — Prep (half day)

- Decide: Marshmallow for rich serialization/validation (recommended) or Cerberus for lightweight rules.
- Add deps: add chosen validation library and `sentry-sdk` to `requirements.txt`/`pyproject.toml`.

Phase 1 — Linting (1 day quick / 1–3 days full cleanup)

- Add config: create `/.pylintrc` with project rules, disable noisy checks initially.
- CI job: add a lint job to CI (run `pylint` against packages).
- Baseline: run `pylint`, generate a report, fix critical/high-priority issues first; defer style-only fixes to later.

Phase 2 — Runtime validation (2–5 days for core flows)

- Create schemas: add `schemas/msme.py` and `schemas/affiliate.py` with Marshmallow/Cerberus schemas for the onboarding and payout payloads.
- Integration: add a small middleware/decorator that validates incoming JSON and returns 400 + structured error payload on failure.
- Handlers: implement validation at handler entry for 2–3 highest-risk endpoints first.
- Tests: add unit tests for schemas and integration tests for handler validation.

Phase 3 — Sentry (1–2 hours basic; 1–3 days full instrumentation)

- Guarded init: implement `observability/sentry.py` that initializes `sentry_sdk.init(dsn=...)` only when `SENTRY_DSN` is set; otherwise no-op. Add support for `environment`, `release`, and `traces_sample_rate` env vars.
- Basic coverage: call guarded init from app startup so exceptions are captured in environments with DSN.
- Instrument workers: add explicit error capture and background job integration (Celery/RQ/async) and add transaction tracing as needed.
- Secrets: document setting `SENTRY_DSN` and release tagging in `docs/` and CI.

Phase 4 — CI, tests, and rollout (1–3 days)

- CI checks: ensure lint + schema tests run on PRs; fail fast for validation regressions.
- Staging: deploy to staging, verify errors appear in Sentry (if DSN present). If no DSN yet, guarded init keeps runtime silent.
- Rollout: after verification, enable DSN in production secrets and monitor.

Per-item time estimates (examples)

- Add `.pylintrc` + CI job: 2–6 hours.
- Baseline lint triage & critical fixes: 0.5–2 days (depends on code health).
- Choose & install validation lib: 1–3 hours.
- Implement 2–3 validation schemas + handler integration: 1–3 days.
- Add guarded Sentry init + basic instrumentation: 1–3 hours.
- Full tracing + worker instrumentation: 1–3 days.

Recommendation for this codebase

- Detected framework: this repository uses FastAPI extensively (multiple services under `services/*` use FastAPI).

- Recommendation: Use FastAPI's built-in Pydantic models for request/response validation where possible (preferred). Reasons:
  - Built-in to FastAPI, minimal glue code and automatic docs/schema generation.
  - High performance, typed, and integrates with dependency injection and test client.
  - Easier to adopt incrementally for handlers already written for FastAPI.

- If you prefer an external validation library:
  - Choose `Marshmallow` over `Cerberus` for richer serialization/deserialization features and a wider ecosystem.
  - Use `Cerberus` only if you need an extremely lightweight rule-based validator and want minimal dependencies.

Practical next steps (minimal friction)

1. Add a guarded Sentry init (`observability/sentry.py`) that no-ops when `SENTRY_DSN` is unset.
2. Start by converting high-risk endpoints to Pydantic request models (MSME onboarding, affiliate payouts) and add tests.
3. Add `pylint` config and a CI lint job; run baseline and fix critical issues.

If you want, I can implement the guarded Sentry init and add an example Pydantic schema + validation middleware in one of the services next.

Prometheus + Grafana (observability)

- Current status: Prometheus client is already present in multiple services and many services expose `GET /metrics` (order-delivery, affiliate-engine, payment-revenue, msme-engine, etc.).
- Goal: central scraping via Prometheus and dashboards/alerts in Grafana.

Recommended steps

- Verify: confirm `/metrics` endpoints across services and ensure consistent metric naming/labels (service, environment, job).
- Dependency: ensure `prometheus_client` is in each service `requirements*.txt` or shared dependency manifest.
- Expose: keep `GET /metrics` (or mount `prometheus_client.asgi.make_asgi_app()` for ASGI) and document the path in each service README.
- Scrape: configure central Prometheus to scrape each service target and set `PROMETHEUS_MULTIPROC_DIR` if using multiprocess mode (e.g., uvicorn/gunicorn workers).
- Dashboards: add Grafana dashboards (import community templates or create custom ones) and store JSON dashboard exports in `infra/observability/grafana/`.
- Alerts: define alerting rules in Prometheus for SLOs (error rate, latency p95/p99, queue depth) and wire to an alertmanager/channel.

Time estimates

- Quick smoke: confirm endpoints + add basic Prometheus config: 1–3 hours.
- Full dashboards + alerts + runbook: 1–3 days.

How this ties to Sentry

- Prometheus/Grafana provides metrics and alerting; Sentry provides crash/error events and traces. Use both: metrics to detect problems; Sentry to triage root causes.

Next step option

- I can (A) implement the guarded Sentry init and add a small `observability/prometheus.py` helper (if you want a single-service example), or (B) add Grafana dashboard JSON templates under `infra/observability/grafana/`. Which do you prefer?