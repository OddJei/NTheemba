Observability helpers for bot-session
===================================

This folder contains small, guarded helpers to enable Sentry and Prometheus
integration without making them hard dependencies of the service.

Usage
-----

The application calls `instrument_app(app)` during startup. The helpers
are best-effort and will no-op when `sentry-sdk` or `prometheus_client`
are not installed or when required environment variables are missing.

Environment variables
---------------------

- `SENTRY_DSN`: when set, the service will attempt to initialize `sentry-sdk`.
- `SENTRY_ENVIRONMENT`: optional Sentry environment tag.
- `SENTRY_RELEASE`: optional release tag for Sentry.
- `SENTRY_TRACES_SAMPLE_RATE`: optional traces sampling rate (float).
- `PROMETHEUS_MULTIPROC_DIR`: when using multiprocess workers, set this to
  the directory used by the Prometheus multiprocess collector.

Dependencies
------------

Install as-needed in your environment or Docker image:

```
pip install sentry-sdk prometheus-client
```
