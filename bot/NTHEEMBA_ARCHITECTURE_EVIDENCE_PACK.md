# Ntheemba Architecture Evidence Pack

Status: local Road 2 evidence pack for the implemented Goals 1-5 baseline.

Date checked: 2026-08-22.

This document records what exists in the active Ntheemba runtime source under
`apps/ntheemba/bot`. It is source and local-test evidence only. It is not
production Apps Script, WhatsApp gateway, Redis, PostgreSQL, or deployment
evidence.

## NDS Orchestrator Context

Task brief:

- Product: Ntheemba neutral conversation runtime.
- Authority: PostgreSQL is the durable business/channel/capability/integration
  source of truth; Redis is a fast runtime/session/cache layer only.
- Scope: Road 2 evidence for the current local Goals 1-5 baseline.
- Non-scope: no app-code changes, no deploy, no production Sheet or gateway
  action, no production reference promotion.

Minimum roster:

- Ntheemba implementation owner: source evidence from the active bot runtime.
- Ntheemba test owner: local unit and validator command evidence.
- Reality/Security gate: limitations and Roads 3-12 gaps are recorded here.

Gate result:

- Local source evidence exists for Goals 1-5 baseline pieces.
- Local tests pass.
- Production readiness remains unproven.

## Capability Catalogue

Exists.

Evidence:

- `ntheemba/domain/capabilities.py` defines the closed `Capability` enum and
  `CapabilityCatalogue.canonical()` with version
  `ntheemba-capabilities-v1`.
- The catalogue owns workflow IDs and TradeFlow operation mappings instead of
  accepting business-supplied workflow names.
- `CapabilityCatalogue.validate_declarations()` separates supported capability
  IDs from unknown declarations.
- `tests/unit/domain/test_capabilities.py` verifies known capability acceptance,
  unknown declaration rejection, operation parsing, and rejection of unknown
  TradeFlow operations.
- `scripts/validate_phase_12.py` includes the self-check
  "Ntheemba-owned capability catalogue rejects unknown declarations".

Limit:

- The catalogue is static source code. Road 3 still needs a controlled runtime
  admin path for changing business configuration without editing seed SQL or
  code.

## Durable Businesses And Channels

Exists.

Evidence:

- `migrations/postgres/001_phase12_core.sql` creates `businesses`,
  `business_channels`, and `business_capabilities`.
- `business_channels` stores provider, business ID, phone number, enabled
  status, and a unique provider/phone constraint.
- `ntheemba/infrastructure/postgres/businesses.py` implements
  `PostgresBusinessRegistry.get_business()`, `get_channel()`,
  `list_businesses()`, and `list_channels()`.
- `migrations/postgres/003_phase12_seed_businesses.sql` seeds local simulator
  businesses and channels for Harvest, AMAC, and Serah's Glow.
- `ntheemba/adapters/businesses/seeds.py` mirrors non-secret development
  business and channel records for local in-memory use.

Limit:

- The seeded channels are simulator placeholders. They are not production
  OpenWA channel registrations.

## Per-Business Capabilities

Exists.

Evidence:

- `business_capabilities` stores `business_id`, `capability_id`, `enabled`, and
  `config JSONB`.
- `PostgresBusinessRegistry._capabilities()` loads only enabled capabilities and
  returns per-capability config.
- `PostgresBusinessRegistry.register_business()` rewrites a business capability
  set and increments `runtime_revision`.
- `RuntimeProfileCompiler` validates loaded declarations through the canonical
  Ntheemba catalogue before compiling a runtime profile.
- `tests/unit/application/test_runtime_profiles.py` verifies Harvest lacks
  booking integration, Serah routes booking through its configured integration,
  capability config is available on the business profile, and capability updates
  invalidate cached runtime profiles.

Limit:

- The write path exists as a service/registry operation. A full operator-facing
  admin path with explicit enable/disable/update workflows is Road 3.

## Business Integrations

Exists.

Evidence:

- `migrations/postgres/004_runtime_profiles_and_integrations.sql` creates
  `business_integrations` with provider, adapter type, base URL, API version,
  auth reference, status, enabled flag, capabilities, and config.
- The migration adds `runtime_revision` to businesses and indexes
  `(business_id, runtime_revision)`.
- `PostgresBusinessRegistry.list_integrations()` loads integrations for one
  business.
- `PostgresBusinessRegistry.register_integration()` updates integration metadata
  and increments the owning business runtime revision.
- `ntheemba/adapters/businesses/seeds.py` provides non-secret local integration
  routes for Harvest, AMAC, and Serah's Glow.
- `tests/unit/application/test_runtime_profiles.py` verifies disabled or
  inactive integrations do not compile into runtime profiles.

Security note:

- The compiled Redis/runtime payload excludes `auth_reference` and integration
  `config`. Source still carries non-secret auth-reference names such as
  `script_properties:NTHEEMBA_API_TOKEN`, not secret values.

## Runtime Profile Compiler

Exists.

Evidence:

- `ntheemba/application/runtime_profiles.py` defines
  `CompiledRuntimeProfile`, `RuntimeProfileCompiler`, and
  `RuntimeProfileConfigurationService`.
- The compiler resolves active channels, active businesses, enabled
  integrations, supported canonical capabilities, and the active business
  `runtime_revision`.
- `CompiledRuntimeProfile.integration_for()` selects an enabled integration for
  a capability only when that capability is enabled for the business.
- `CompiledRuntimeProfile.to_json()` serializes routing metadata for cache use.
- `CompiledRuntimeProfile.from_json()` rejects cached profiles for the wrong
  channel or business.
- `tests/unit/application/test_runtime_profiles.py` verifies channel-scoped
  cache entries, stale revision rejection, Redis-loss reload from the registry,
  and cache invalidation on capability or integration updates.

Limit:

- Tests use fakes or local in-memory adapters. They prove local behavior, not
  deployed PostgreSQL or Redis behavior.

## Redis Cache Shape

Exists as a revisioned cache shape.

Evidence:

- `ntheemba/infrastructure/redis/runtime_profiles.py` stores compiled runtime
  profiles by business ID, channel instance ID, and runtime revision.
- The Redis cache maintains a per-business profile index so
  `invalidate(business_id)` can delete stale cached profile keys.
- `CompiledRuntimeProfile.to_json()` omits channel phone numbers, capability
  config, integration config, and integration auth references.
- `tests/unit/application/test_runtime_profiles.py` verifies cached payloads
  exclude phone numbers, private capability values, integration config, auth
  references, token names, and private API key fields.
- `tests/unit/infrastructure/test_redis_phase12_adapters.py` covers Redis
  session, idempotency, deduplication, lock, and runtime-profile adapter
  behavior against an in-process Redis protocol double.

Limit:

- Road 4 still needs full runtime cache finalization: deployed Redis loss
  rebuild proof, stale cache invalidation proof against real stores, and
  operational redaction verification.

## Guard Pieces

Exists partially and is active in local runtime composition.

Evidence:

- `ntheemba/application/capability_runtime.py` defines
  `BusinessContextResolver`, `CapabilityRequirementPolicy`, and
  `CapabilityAwareWorkflowRouter`.
- `BusinessContextResolver` validates exact channel instance, provider, and
  recipient phone before business context is returned.
- Unknown business capability declarations are recorded through
  `UnsupportedDeclarationSink`.
- `CapabilityRequirementPolicy` maps intents and active flows to canonical
  required capabilities.
- `CapabilityAwareWorkflowRouter` blocks workflow execution and emits a
  `capability.denied` event when required capabilities are missing.
- `ntheemba/adapters/tradeflow/contract.py` defines
  `CapabilityControlledTradeFlowAdapter`, `DynamicTradeFlowIntegrationResolver`,
  `NtheembaTradeFlowIngress`, and `IdempotentTradeFlowContractAdapter`.
- `tests/unit/application/test_capability_runtime.py` verifies unknown
  declarations are recorded and empty capability context blocks booking before
  workflow execution.
- `tests/unit/application/test_runtime_profiles.py` verifies Harvest booking is
  denied without adapter factory invocation and Serah booking uses the Serah
  configured integration.

Limit:

- Road 5 remains open because the complete guard matrix still needs end-to-end
  proof for every operation: known capability, global support, business-enabled
  support, configured enabled integration, supported operation, valid workflow
  transition, and required inputs.

## Adapter Pieces

Exists partially.

Evidence:

- `ntheemba/domain/tradeflow_contract.py` defines the Ntheemba-owned TradeFlow
  operation catalogue and maps operations to capabilities.
- `ntheemba/ports/tradeflow_contract.py` defines the contract adapter port.
- `ntheemba/adapters/tradeflow/contract.py` contains deterministic in-memory
  adapter tests, capability-controlled execution, dynamic integration resolver,
  raw operation parsing/rejection, and idempotency protection for write
  operations.
- `tests/unit/adapters/tradeflow/test_contract.py` verifies capability-controlled
  adapter behavior, unsupported operation observation, and idempotent write
  handling.
- `tests/unit/adapters/tradeflow/test_runtime_port.py` verifies the runtime
  TradeFlow port wiring.

Limit:

- Road 6 remains open because a complete live common dynamic TradeFlow adapter
  contract, real integration resolver behavior, and optional-operation failure
  proof against non-fake adapters are not complete production evidence.

## Interpreter Pieces

Exists partially.

Evidence:

- `ntheemba/services/interpretation.py` provides `HybridInterpreter`, rule-first
  interpretation, model fallback, and a model context that includes
  `enabled_capabilities`.
- `ntheemba/services/validation.py` validates model output shape, supported
  intent enums, supported entity fields, confidence threshold, and restricted
  business-fact fields.
- `tests/unit/services/test_validation.py` verifies model payload conversion,
  low-confidence clarification, external business fact rejection, unknown entity
  field rejection, and unsupported intent rejection.
- `tests/unit/application/test_service.py` verifies enabled capabilities are
  passed into interpreter calls and duplicate messages do not interpret or
  publish twice.

Limit:

- Road 7 remains open because allowed-action context is present but the broader
  capability-aware interpreter contract still needs explicit proof that model
  proposed unavailable actions are rejected for each business profile and that no
  business-type bot branching exists across the whole runtime.

## Local Test Evidence

Commands run from `apps/ntheemba/bot` on 2026-08-22:

```text
python -m pytest tests/unit
```

Result:

```text
336 passed, 1 warning in 4.23s
```

Warning:

```text
StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.
```

```text
python scripts/validate_phase_12.py
```

Result:

```json
{
  "checks": [
    "Ntheemba-owned capability catalogue rejects unknown declarations",
    "versioned session serialization preserves seven-day runtime state",
    "authenticated gateway ingestion queues a normalized message",
    "PostgreSQL migrations include tenant isolation and retention",
    "durable idempotency contract prevents duplicate action claims",
    "cross-business name reuse requires explicit consent"
  ],
  "status": "passed"
}
```

## Remaining Gaps For Roads 3-12

Road 3 - Runtime configuration admin path:

- Partial: registry and configuration service can register businesses and
  integrations and invalidate runtime cache.
- Gap: controlled operator/admin workflow, authorization boundary, revision bump
  behavior for every config mutation, and tests such as "disable Serah booking
  increments revision and next runtime excludes booking".

Road 4 - Redis runtime cache finalization:

- Partial: revisioned profile cache, invalidation, redacted payload tests.
- Gap: real Redis rebuild proof, stale cache invalidation proof against
  configured stores, and operational redaction checks.

Road 5 - Integration-aware guard:

- Partial: capability-aware workflow router, dynamic integration resolver,
  TradeFlow operation parsing, idempotent write adapter.
- Gap: complete guard matrix and end-to-end tests for all supported operations
  and required input validation before external calls.

Road 6 - Common dynamic TradeFlow adapter:

- Partial: common operation catalogue, adapter port, resolver, reference/fake
  adapters.
- Gap: production-shaped common adapter implementation with dynamic tenant
  integration binding and safe optional-operation failure across real configured
  adapters.

Road 7 - Capability-aware interpreter:

- Partial: interpreter receives enabled capabilities and model context includes
  them; model output validator rejects unsupported intents and business facts.
- Gap: explicit unavailable-action rejection for model-proposed actions by
  business profile, and whole-repo proof of no business-type bot classes or
  workflow branching.

Road 8 - Generic workflow completion:

- Partial: information, catalogue, order, booking, and handover workflow modules
  and unit tests exist.
- Gap: proof that every workflow is fully generic and capability-driven for any
  enabled business, with negative tests for businesses lacking capabilities.

Road 9 - NCPC product resolution:

- Partial: product resolver, NCPC ports, catalogue/order tests, and selection
  handling exist.
- Gap: full customer-confirmed NCPC to TradeFlow item flow, stale selection,
  multiple match, barcode/alias/size-warning, and two-business isolation proof.

Road 10 - Reliability, privacy, observability:

- Partial: tracing, audit events, deduplication, idempotency, handover, failure
  fallback, and local tests exist.
- Gap: production-grade redacted structured events, correlation proof, retry
  behavior, failed authoritative call recovery, and log privacy verification.

Road 11 - Local two-business proof:

- Partial: local seed businesses and simulator channels exist.
- Gap: one consolidated evidence report proving Harvest catalogue/order allowed,
  Harvest booking denied with no API call, Serah catalogue/services/booking
  allowed, Redis reload works, and no URL/cache/session leakage.

Road 12 - Independent gate and test deployment readiness:

- Partial: local source and test evidence exists.
- Gap: independent security review, independent reality review, release
  checklist, rollback plan, test environment config checklist, and no
  Critical/High tenant, secret, auth, source-root, or deployment issue.

## Reviewer Reading Path

Start with:

1. `NTHEEMBA_IMPLEMENTATION_ROADMAP.md`
2. `GOALS_1_5_RUNTIME_BASELINE.md`
3. `ntheemba/domain/capabilities.py`
4. `migrations/postgres/001_phase12_core.sql`
5. `migrations/postgres/004_runtime_profiles_and_integrations.sql`
6. `ntheemba/application/runtime_profiles.py`
7. `ntheemba/application/capability_runtime.py`
8. `ntheemba/adapters/tradeflow/contract.py`
9. `ntheemba/services/interpretation.py`
10. `tests/unit/application/test_runtime_profiles.py`

This should let a reviewer verify current implementation status without reading
the whole codebase.
