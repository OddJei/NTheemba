# Ntheemba — Phase 12 Durable Capability-Neutral Runtime

This repository contains the foundation for the Ntheemba conversation and workflow engine.

## Requirements

- Python 3.12 or newer
- Docker Desktop for the local Redis/PostgreSQL profile

## Local setup

```bash
python -m venv .venv
```

Activate the environment:

```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# Linux or macOS
source .venv/bin/activate
```

Install the project:

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Copy the environment template:

```bash
# Windows
copy .env.example .env

# Linux or macOS
cp .env.example .env
```

Start the Phase 12 data services and migrate PostgreSQL:

```bash
docker compose -f docker-compose.phase12.yml up -d
python scripts/migrate_postgres.py --dsn "postgresql://ntheemba:ntheemba_local_change_me@localhost:5432/ntheemba"
python scripts/validate_storage.py
```

Start FastAPI:

```bash
python -m uvicorn ntheemba.main:app --reload
```

Open:

- API documentation: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`
- Readiness: `http://127.0.0.1:8000/ready`
- Developer console: `http://127.0.0.1:8000/dev/console` (development/test only)
- Conversation simulator: `http://127.0.0.1:8000/dev/simulator` (development/test only)
- Multi-conversation workspace: `http://127.0.0.1:8000/dev/simulator/workspace` (development/test only)
- Storage diagnostics: `http://127.0.0.1:8000/dev/storage` (development/test only)

## Quality commands

```bash
pytest
ruff check .
ruff format --check .
mypy ntheemba tests
```

## Phase 0 scope

Phase 0 provides:

- FastAPI application factory;
- environment-based settings;
- health and readiness endpoints;
- structured application errors;
- exception handlers;
- linting, formatting, typing, and test configuration;
- no required Redis, NCPC, TradeFlow, OpenWA, or LLM connection.

External adapters are added in later phases.


## Phase 1 domain foundation

The project now includes pure domain models for conversation flows, typed intents, order and booking drafts, product resolution, session lifecycle, and central transition authorization. See `PHASE_1_DOMAIN.md`.


## Phase 2 ports and test fakes

The project now defines technology-independent ports for sessions, locks,
deduplication, outgoing publication, audits, NCPC, and TradeFlow. In-memory
fakes allow Phase 3 application orchestration to be tested without Redis,
HTTP services, queues, or live business systems.

See `PHASE_2_PORTS_AND_FAKES.md`.


## Phase 3 application orchestration

The project now includes a testable message-processing pipeline with session
coordination, transition-authorized workflow routing, deduplication, rollback,
audit events, and ordered outgoing publication.

See `PHASE_3_APPLICATION.md`.


## Phase 4 interpretation and validation

The project now includes a rule-first hybrid interpreter, pending-answer
classification, safe workflow interruptions, correction targeting, constrained
model fallback, and strict validation of model-proposed entities.

See `PHASE_4_INTERPRETATION.md`.

## Phase 5 response builder

Customer-facing text and image reply instructions are now centralized in
`ntheemba/services/response_builder.py`. The builder is pure, customer-safe,
length-bounded, ID-redacting, Decimal-based, and independently tested.

See `PHASE_5_RESPONSE_BUILDER.md`.

## Phase 6 information workflow

The project now includes the first real workflow handler for public business
information, opening hours, and approved FAQs. It safely suspends and restores
catalogue, order, and booking conversations when customers ask side questions.

See `PHASE_6_INFORMATION_WORKFLOW.md`.

## Phase 7 human handover

The project now supports customer handover requests, human waiting and active
states, trusted staff takeover, bot resumption with exact workflow restoration,
conversation closure, and application-level bot suppression during human
control.

See `PHASE_7_HANDOVER_WORKFLOW.md`.

## Phase 8 NCPC product resolver

The project now resolves natural product language and barcodes through NCPC,
filters candidates through each business's TradeFlow catalogue, handles
relative sizes, produces controlled clarification or confirmation, and resolves
validated customer selections into exact business products.

See `PHASE_8_PRODUCT_RESOLVER.md`.

## Phase 9 product catalogue workflow

The project now supports product searches, saved candidate clarification,
contextual YES confirmation, numbered/name/size selection, current TradeFlow
product details and images, invalid-selection escalation, and reuse inside the
future order flow.

See `PHASE_9_CATALOGUE_WORKFLOW.md`.

## Phase 10 order workflow

The project now supports complete product-order request collection: product
resolution, quantity, collection or delivery, customer details, live stock and
price validation, review, correction, cancellation, fresh confirmation, and
idempotent TradeFlow submission.

See `PHASE_10_ORDER_WORKFLOW.md`.

## Phase 11 booking workflow

The project now supports service search, appointment dates, live slot choices, optional staff preference, customer details, review, correction, fresh confirmation, and idempotent TradeFlow booking submission.

See `PHASE_11_BOOKING_WORKFLOW.md`.

## Phase 11.1 — Observability foundation

The core now includes immutable execution-trace events, asynchronous trace-context
propagation, a technology-independent `TraceSink`, reusable span lifecycle management,
and an async tracing decorator. Business workflows are not instrumented yet; that is
Phase 11.2.

## Phase 11.4 — Developer Test API

Development and test environments expose trace inspection endpoints under `/dev`. See `PHASE_11_4_DEVELOPER_TEST_API.md` for endpoint and architecture details.

## Phase 11.5 — Developer Test Console

Development and test environments expose a browser console at `/dev/console` for trace inspection, conversation filtering, trace-store health and reset operations. See `PHASE_11_5_DEVELOPER_TEST_CONSOLE.md`.

## Phase 11.6 — Fake Dependency Controls

The developer console and API now provide deterministic, bounded controls for fake TradeFlow, NCPC, publishing, session, deduplication, locking, audit and interpretation boundaries. Developers can inject latency, one-shot failures, persistent failures and operation-specific fault plans without exposing controls in staging or production.

See `PHASE_11_6_FAKE_DEPENDENCY_CONTROLS.md`.

## Phase 11.7 — Developer Tooling Security

Developer tooling is now protected by explicit environment/enablement gating, loopback-only network access by default, optional Bearer authentication, cross-origin rejection, defensive no-cache/security headers, nonce-based console CSP, OpenAPI exclusion, and recursive trace-attribute redaction. Non-loopback networks require a developer token of at least 32 characters.

See `PHASE_11_7_DEVELOPER_TOOLING_SECURITY.md`.


## Phase 11.8 — Observability Validation and Completion

Retained traces can now be validated as execution graphs for lifecycle, parentage, uniqueness, root-span, and correlation integrity. Validation is available for one trace or the complete in-memory snapshot.

See `PHASE_11_8_OBSERVABILITY_VALIDATION.md`.

## Phase 11.9 — Production Observability Bridge

The application factory now creates an application-wide tracer and composes a production-safe structured-log exporter with the developer memory sink when appropriate. Exported attributes are redacted and bounded, trace sampling is deterministic, and failed events always bypass sampling.

See `PHASE_11_9_PRODUCTION_OBSERVABILITY_BRIDGE.md`.

## Phase 11.10 — Observability Operational Readiness

Observability now has fail-open per-sink runtime counters, readiness reporting, protected runtime diagnostics, and a dependency-free synthetic self-check suitable for CI and deployment verification.

See `PHASE_11_10_OPERATIONAL_READINESS.md`.


## Phase 11.11 — Developer Conversation Simulator

Development and test environments now include a protected WhatsApp-style chat simulator at `/dev/simulator`. Messages travel through the real `NtheembaService` pipeline and the existing catalogue, order, booking, information, handover, session, dependency, publisher, and tracing boundaries. The UI displays live pipeline stages, session state, replies, replay/deduplication behavior, and dependency-injected failures.

See `PHASE_11_11_DEVELOPER_CONVERSATION_SIMULATOR.md`.


## Phase 11.12–11.20 — Capability-Neutral Multi-Business Runtime

Ntheemba now owns a closed canonical capability and TradeFlow-operation catalogue.
Connected TradeFlow businesses only declare support for Ntheemba-known capabilities.
Unknown capability names or methods are rejected, recorded for review, and never
auto-enabled.

The runtime now includes:

- exact receiving-channel business resolution before interpretation;
- business-specific capability loading and enforcement;
- one reusable workflow library for standard and customised businesses;
- minimal platform customers plus private business-client links;
- Serah client recognition, appointment, product, and loyalty examples;
- Standard TradeFlow product/order examples;
- cross-business customer recognition with isolated sessions;
- versioned TradeFlow request/response contracts;
- Standard and Serah reference adapter boundaries;
- legacy OpenWA envelope translation;
- claim/ack/retry gateway queue semantics for the later Redis Streams adapter;
- a grouped multi-conversation developer workspace.

Read `PHASE_11_12_TO_11_20_CAPABILITY_NEUTRAL_RUNTIME.md` for the complete
architecture and `PHASE_11_20_VALIDATION.md` for the quality gate.

### Phase 11.20 synthetic validation

```bash
python scripts/validate_phase_11_20.py
```

Phase 12 may replace the current in-memory adapters with Redis and PostgreSQL,
but it must preserve the Phase 11.20 capability, gateway, customer, and adapter
contracts.


## Phase 12 — Durable runtime state and customer memory

Phase 12 rebuilds persistence on top of the frozen Phase 11.20 contracts. Ntheemba
remains the only owner of capability definitions and TradeFlow operation meanings.
PostgreSQL stores business declarations and unknown observations, but loading a row
never creates a capability: every declaration is validated against
`CapabilityCatalogue.canonical()` before use.

Phase 12 provides:

- Redis JSON sessions with optimistic revisions, seven-day active TTL, and 90-day archives;
- Redis distributed conversation locks;
- Redis message deduplication and 30-day external-action idempotency;
- acknowledged Redis Streams for inbound/outbound gateway delivery, stale claim recovery, retry, and dead-letter handling;
- PostgreSQL businesses and exact receiving-channel mappings;
- minimal platform customers and private business-client links;
- explicit consent for cross-business name reuse, saved checkout details, raw-message retention, and marketing;
- tenant-isolated addresses, preferences, messages, summaries, and question analytics;
- retained observations of unknown capabilities and TradeFlow methods without activation;
- retention cleanup, readiness checks, developer diagnostics, and Windows-compatible Psycopg startup;
- an authenticated `/api/v1/gateway/inbound` ingestion endpoint.

Run the dependency-free Phase 12 contract check:

```bash
python scripts/validate_phase_12.py
```

Run the external service check after Docker and migrations:

```bash
python scripts/validate_storage.py
```

See `PHASE_12_DURABLE_RUNTIME_AND_CUSTOMER_MEMORY.md` and
`PHASE_12_VALIDATION.md`.
