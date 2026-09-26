# Phase 11.6 — Fake Dependency Controls

Phase 11.6 adds a development-only control plane for simulating dependency latency and failures without changing workflow code or connecting to live systems.

## Controlled boundaries

The default registry includes:

- `tradeflow`
- `ncpc`
- `publisher`
- `session_repository`
- `session_lock`
- `deduplication`
- `audit`
- `interpreter`

The controller is reusable by any fake adapter through either:

```python
await controller.before_call("tradeflow", "create_order_request")
```

or:

```python
result = await controller.run("tradeflow", "create_order_request", operation)
```

## Behavior model

Each dependency has an independent in-memory behavior:

- `latency_ms`: adds 0–30,000 milliseconds before matching calls;
- `fail_next`: fails the next 0–100 matching calls, then returns to normal;
- `always_fail`: persistently fails matching calls until reset;
- `failure_message`: bounded developer-visible failure text;
- `operations`: optional exact operation allow-list; an empty list targets all operations.

`fail_next` tokens are consumed under an async lock, so concurrent callers cannot consume the same one-shot failure.

## Developer API

The routes are registered only in `development` and `test` environments.

```text
GET    /dev/dependencies
GET    /dev/dependencies/{dependency}
PUT    /dev/dependencies/{dependency}
DELETE /dev/dependencies/{dependency}
POST   /dev/dependencies/reset
POST   /dev/dependencies/{dependency}/probe
```

Example configuration:

```json
{
  "latency_ms": 500,
  "fail_next": 1,
  "always_fail": false,
  "failure_message": "TradeFlow test outage",
  "operations": ["create_order_request"]
}
```

The probe endpoint executes the configured pre-call behavior without touching a real service. It is useful for confirming latency, operation filters, one-shot failure consumption and persistent failure settings.

## Developer console

`GET /dev/console` now includes a **Fake dependency controls** panel that can:

- select a registered dependency;
- configure latency and one-shot failures;
- enable or disable persistent failure;
- target specific operation names;
- set a bounded failure message;
- probe the active behavior;
- reset one dependency or the complete registry.

The existing trace browser remains available in the same console.

## Safety boundaries

- Controls are not registered in staging or production.
- State is process-local and memory-only.
- Dependency names are selected from a fixed registry.
- Operation names and messages are validated and length-bounded.
- Latency and failure counters have hard upper limits.
- The console retains no-store, CSP and anti-framing headers.
- No live credentials or live dependency configuration is accepted.

## Validation

```text
248 tests passed
Ruff passed
Ruff formatting passed
MyPy strict passed
```
