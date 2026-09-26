# Ntheemba Implementation Status

Status: `SOURCE_LOCAL_INTEGRATION_READY / DEPLOYED_RUNTIME_EVIDENCE_PENDING`

## 2026-09-04 Marketplace platform-source iterations

Owner direction explicitly allowed continued local/source Ntheemba implementation while keeping deployment/live-system restrictions intact. Current source checkpoints:

- `NTHEEMBA_CHANNEL_AND_PLATFORM_CONTEXT_SOURCE_READY`
- `NTHEEMBA_MARKETPLACE_DETERMINISTIC_CORE_SOURCE_READY`
- `NTHEEMBA_MARKETPLACE_PRODUCT_DISCOVERY_SOURCE_READY`
- `NTHEEMBA_MARKETPLACE_HANDOFF_SOURCE_READY`

Marketplace is PLATFORM-only and cannot be assigned to any business capability set. Cross-business Marketplace product discovery requires trusted NCPC identity. Selection creates an explicit persisted business handoff context without creating an order. WAHA/WhatsApp and LLM remain out of scope for these iterations.


## Frozen baseline

On 2026-09-03 implementation resumed by explicit owner direction without a
commit, deployment, production access, or live configuration change. Historical
baseline evidence remains preserved: the repository started from commit
`636143c323e1a1b483df44c05bd6ffdab6c1dcb6` plus a pre-existing dirty worktree.
Historical baseline test/lint/type results are evidence of the starting state and
are not overwritten by the newer integration checkpoint.

## 2026-09-04 deterministic integration checkpoint

Ntheemba now has source/local production-shaped boundaries for:

- shared NCPC HTTP identity resolution;
- tenant-specific TradeFlow HTTP clients selected from business integration config;
- secret references rather than stored secret material;
- secure runtime-profile cache rehydration from the durable registry;
- same-tenant TradeFlow fallback when NCPC misses;
- provisional pending-review products without fabricated NCPC IDs;
- multi-shop `shop_id` propagation into availability/order submission;
- two-business HTTP-level tenant-isolation tests;
- reusable deterministic runtime composition;
- authenticated operator control-plane mutations and operational auditing.

Catalogue visibility follows `DEC-2026-09-04-001`: unsubmitted/local-only/
rejected products remain TradeFlow-operational but hidden from Ntheemba;
pending-review products are provisional within the resolved business; linked
products require explicit business publication.

## Current local evidence

- Standard TradeFlow: `node --test tests/*.test.mjs` -> **20 passed**.
- Standard TradeFlow source parse -> **passed**.
- Ntheemba focused integration/control-plane gate -> **81 passed**.
- Ntheemba broader available sandbox suite -> **464 passed** with the
  PostgreSQL-specific unit file excluded only because this sandbox lacks
  `psycopg`.
- `python scripts/validate_phase_12.py` -> **passed**.
- Ntheemba `compileall` -> **passed**.
- NCPC service -> **18 passed** against SQLite test configuration.
- NCPC `compileall` -> **passed**.
- Scoped `git diff --check` -> **passed**.

Full evidence and limitations are recorded in:
`Docs/roadmap/NTHEEMBA-NCPC-TRADEFLOW-INTEGRATION-READINESS.md`.

## Environment limitations

The repository declares `psycopg`, `redis`, `ruff` and `mypy`, but they are not
installed in this sandbox. Package installation was attempted and blocked by the
sandbox's lack of package-network access. Therefore the PostgreSQL-specific test
file, real PostgreSQL/Redis connectivity and new Ruff/mypy results are not
claimed as completed by this checkpoint.

## Still not production proof

No deployed Standard TradeFlow Web App, live Google Sheet, Script Properties,
real NCPC endpoint, named non-production PostgreSQL/Redis environment, real
WhatsApp gateway, production secret, commit, or push was used. Two-business
**deployed** staging, restart/recovery, backup/restore, runtime security review
and production operations evidence remain future gates.

## Next engineering gate

Freeze this source/local deterministic baseline before adding the LLM
interpretation adapter. LLM interpretation must remain replaceable and behind
business resolution, capability guards and deterministic workflow validation.
WhatsApp transport remains a later gate.

## 2026-09-04 channel and platform-context iteration

Ntheemba now models channel ownership independently from any specific WhatsApp
implementation. The exact external routing identity is:

`(provider, external_session_id, recipient_identifier)`

A channel is explicitly scoped as either `BUSINESS` or `PLATFORM`:

- `BUSINESS` channels require a `business_id` and may use only business roles.
- `PLATFORM` channels must not have a `business_id` and use Ntheemba-owned roles
  such as `marketplace`, `platform_general`, or `platform_support`.
- Marketplace is represented by the separate `PlatformCapability.MARKETPLACE`.
  It is not present in the business `CapabilityCatalogue`, cannot be declared in
  `BusinessProfile`, is rejected by the operator control plane, and is forbidden
  by PostgreSQL constraint on `business_capabilities`.
- Channel ownership is immutable across business/platform scopes.
- Duplicate exact external channel identities are rejected.
- Only one primary channel per owner/role is allowed; registering a new primary
  Marketplace channel clears the previous primary in the in-memory control
  plane and PostgreSQL enforces the same uniqueness.
- Platform Marketplace resolution returns `ResolvedPlatformContext` with no
  tenant business or TradeFlow integration.
- Existing deterministic business workflows continue through
  `ResolvedBusinessContext`; platform channels fail closed if passed directly to
  the business-only resolver.

PostgreSQL migration:
`migrations/postgres/006_channel_scope_and_platform_context.sql`.

### Channel/platform local evidence

- Focused channel/domain/operator/runtime/migration/API gate: **46 passed**.
- Broader Ntheemba available regression: **475 passed** with only the pre-existing
  unfinished inbound-runtime test and PostgreSQL-specific unit test excluded.
- The inbound-runtime test remains outside this iteration because its existing
  fixture references a missing `InMemoryNCPCAdapter`.
- The PostgreSQL-specific unit file remains blocked in this sandbox by missing
  `psycopg`; migration safety is covered by static tests here.

### Next Ntheemba-only gate

Build the deterministic PLATFORM/Marketplace core on top of
`ResolvedPlatformContext` without implementing WAHA or an LLM. Business
capabilities must remain permanently unable to include Marketplace.

## 2026-09-04 N13-N15 checkpoint

Checkpoint: `NTHEEMBA_HANDOFF_ORDER_WORKFLOW_CONVERGENCE_SOURCE_READY`

- N13: Marketplace handoffs now have an explicit durable `READY -> CONSUMED` transition with business revision, integration, NCPC trust, exact shop, availability and price revalidation.
- N14: consumed Marketplace handoffs enter the existing business order workflow; TradeFlow remains order authority and `MPORDER:<handoff_id>` is the stable mutation idempotency key.
- N15: normal business contexts and consumed Marketplace contexts now share `BusinessExecutionContext` and `BusinessWorkflowRuntime`; NtheembaService uses the same runtime for trusted business-context workflow execution.
- HTTP two-tenant order proof verifies the selected BUS-A endpoint/token is used and BUS-B is never contacted.
- A latent TradeFlow HTTP `_shop_data` bug affecting nested order payloads was fixed.

Validation: focused gate 39 passed; broad available Ntheemba suite 508 passed; Phase 12 validator PASS; compileall PASS. Literal full pytest remains blocked only by missing sandbox `psycopg` for the PostgreSQL-specific unit module.

## 2026-09-04 N16-N18 checkpoint

Checkpoint: `NTHEEMBA_PLATFORM_ROUTING_GENERIC_WORKER_SESSION_HARDENING_SOURCE_READY`

### N16 - Platform workflow router

- Added a deterministic `PlatformWorkflowRouter` operating only on `ResolvedPlatformContext`.
- Marketplace PLATFORM conversations now support search, result selection, explicit handoff readiness, explicit business entry, reset/cancel and business continuation without creating a fake tenant session.
- Non-Marketplace PLATFORM roles return a safe deterministic platform response instead of entering a tenant workflow or being retried as an application error.
- Marketplace remains impossible to grant as a business capability.

### N17 - Generic inbound runtime worker

- Added provider-neutral `UnifiedGatewayMessageService` behind the existing reliable inbound worker.
- Exact channel resolution occurs before workflow routing:
  - BUSINESS -> existing deterministic tenant runtime;
  - PLATFORM -> platform session + platform workflow router.
- Platform replies use `scope=PLATFORM`, preserve the exact originating channel/role and carry no fake `business_id`.
- A consumed Marketplace handoff can enter the normal business workflow through the N13-N15 `BusinessWorkflowRuntime` while the source channel remains PLATFORM.
- Gateway worker typing now depends on a generic inbound processor protocol rather than the business-only concrete gateway service.

### N18 - Session and transition hardening

- Added separate `PlatformConversationSession`, coordinator, in-memory repository/locks and Redis repository/locks.
- Platform session keys are isolated by `(channel_instance_id, customer_id)` and serialize independently of tenant sessions.
- Marketplace business continuation records the exact durable business `conversation_id`.
- Missing/replaced business sessions fail closed back to `HANDOFF_READY` rather than attaching to a different conversation.
- Explicit `continue` can safely re-enter after the handoff is revalidated.
- Stale selected-business runtime/handoff state resets Marketplace rather than switching tenant/integration implicitly.
- Redis platform session repository now validates positive transaction retry configuration.

### N16-N18 local evidence

- Focused platform/router/worker/session/Redis/service gate after final cleanup: **30 passed**.
- Broader Ntheemba available regression before documentation freeze: **519 passed** with only the PostgreSQL-specific unit module excluded because this sandbox lacks `psycopg`.
- Redis gateway platform-envelope round trip: PASS.
- Phase 12 validator: PASS.
- `compileall`: PASS.
- Source whitespace/style cleanup for the new N16-N18 files: PASS.

### Environment/runtime limitations

The literal full pytest collection still cannot import `tests/unit/infrastructure/test_postgres_businesses.py` because `psycopg` is not installed in this sandbox. Ruff and mypy are also unavailable here. This checkpoint therefore claims source/local deterministic readiness only, not PostgreSQL/Redis deployed-runtime or production readiness.

### Next engineering batch

N19-N21 should harden idempotency/deduplication, downstream failure/resilience behavior, and observability/audit completeness on top of this now-unified BUSINESS/PLATFORM runtime. WAHA/WhatsApp and LLM integration remain later splits.

## 2026-09-04 N19-N21 checkpoint

Checkpoint: `NTHEEMBA_IDEMPOTENCY_RESILIENCE_OBSERVABILITY_SOURCE_READY`

### N19 - Generic idempotency/deduplication

- Added provider-neutral ingress idempotency before BUSINESS/PLATFORM workflow execution.
- Key scope is provider + exact channel + provider message ID; phone numbers are excluded from storage keys.
- Duplicate PLATFORM messages are acknowledged before Marketplace/session mutation.
- Retryable failures release the ingress claim; successful/final handling completes it; terminal dead letters persist failed claims.
- Existing business message deduplication, outbound reply idempotency and TradeFlow mutation idempotency remain independent defense-in-depth layers.

### N20 - Failure/resilience hardening

- Added deterministic worker failure classification.
- NCPC/TradeFlow unavailable errors are retryable; malformed/rejected response errors are terminal.
- Connection/timeouts retry only inside the configured delivery-attempt budget.
- Terminal failures and exhausted attempts dead-letter without switching tenant integrations or marketplace scope.

### N21 - Observability/audit completion

- Inbound/outbound worker delivery spans are correlated by request/message ID.
- Worker audit covers duplicate, acknowledge, retry, send and dead-letter outcomes.
- Audit is fail-open and records only safe routing/action metadata.
- Worker snapshots expose acknowledged/duplicate/retried/dead-lettered counters.
- Platform workflow actions are traced and audited under the Ntheemba platform partition.
- Developer simulator now exposes a safe `/dev/simulator/audit` endpoint alongside trace/replay/fault controls.

### N19-N21 local evidence

- Broad available Ntheemba regression: **526 passed** with only the PostgreSQL-specific unit module excluded because this sandbox lacks `psycopg`.
- Phase 12 validator: PASS.
- Python `compileall`: PASS.
- WAHA/WhatsApp and LLM code remain out of scope.

### Next engineering batch

N22-N24: security/tenant-isolation hardening, real PostgreSQL/Redis runtime/migration/restart proof, and deterministic two-business staging evidence.

## 2026-09-04 N22-N24 checkpoint

Checkpoint: `NTHEEMBA_N22_N24_SOURCE_READY_REAL_RUNTIME_PENDING`

### N22 - Security and tenant-isolation hardening

- Canonical external channel identities now prevent provider-case/whitespace routing bypasses.
- NCPC and TradeFlow dependency configuration rejects literal localhost/private/link-local endpoints.
- Integration auth/config rejects raw secret values in favour of opaque references.
- PostgreSQL migration `010_runtime_security_hardening.sql` enforces Marketplace source-channel and integration-tenant ownership at direct persistence level.

### N23 - Real runtime proof readiness

- Added idempotent ordered migration discovery/application.
- Docker Compose now runs `ntheemba-migrate` before the API and defines the explicit standalone worker profile.
- Added `validate_n23_runtime.py` plus opt-in live PostgreSQL/Redis tests and restart-proof procedure.
- Current sandbox real-runtime result is BLOCKED because `psycopg`, `redis`, PostgreSQL and Redis services are unavailable here. No deployed/runtime completion claim is made.

### N24 - Two-business deterministic staging

- Added deterministic two-business Marketplace-to-order staging with BUS-A/B endpoint/token isolation.
- Selection/consumption/order bind to the selected tenant and exact shop.
- Cross-platform-channel handoff use and stale runtime revision fail closed before tenant HTTP calls.
- Duplicate order confirmation does not create a second TradeFlow mutation.

### N22-N24 final local evidence

- Focused N22-N24 gate: **49 passed**.
- Full available Ntheemba suite: **552 passed, 3 skipped**.
- Phase 12 validator: PASS.
- Python compileall: PASS.
- Docker Compose parse: PASS.
- N23 live runtime remains the only batch gate pending external non-production PostgreSQL/Redis evidence.

## 2026-09-04 independent freeze review

Checkpoint retained: `NTHEEMBA_N22_N24_SOURCE_READY_REAL_RUNTIME_PENDING`.

- Corrected a stale PostgreSQL registry test so it verifies that immutable ownership and exact-identity locks run *before* channel upsert; it no longer asserts the obsolete insert-first sequence.
- Current local full suite: **555 passed, 2 skipped**. The two skips are the explicitly opt-in N23 live PostgreSQL/Redis tests; `psycopg` and `redis` are now installed in this review environment.
- Current focused N22-N24 regression: **26 passed**; Phase 12 validator, `compileall`, and migration-plan discovery pass.
- Root local Compose configuration parses successfully. A permitted Docker proof attempt was blocked before any service started because Docker Desktop timed out pulling the Redis image from Docker Hub. This is an environment/image-availability blocker, not real PostgreSQL/Redis runtime evidence.
- Current static-quality gap: Ruff reports **171** findings and strict mypy reports **44** errors. The legacy documentation statements that the tools/packages are unavailable are stale; these quality failures remain release blockers unless independently accepted and remediated.
