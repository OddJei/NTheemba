# Ntheemba Runtime Baseline: Goals 1-5

Status: local implementation baseline, not production deployment evidence.

This baseline records source and runtime behavior only. It does not include archived inputs,
tenant identity, deployment identity, credentials, or live runtime state.

## Active runtime source

The active local Ntheemba runtime source root is:

`apps/ntheemba/bot`

Legacy Docker/runtime copies and archived source are not production roots. A local Docker stack may be rebuilt later from this root only after explicit environment approval.

## Goal 1: Canonical capability model

Ntheemba owns a closed, versioned capability catalogue:

- catalogue version: `ntheemba-capabilities-v1`
- implementation: `ntheemba/domain/capabilities.py`
- unknown capabilities are rejected and can be recorded as unsupported observations.

Completion test:

- `tests/unit/domain/test_capabilities.py`

## Goal 2: Durable business registry

PostgreSQL owns businesses, exact WhatsApp/provider channels, enabled status, and runtime revisions.

Implementation:

- `migrations/postgres/001_phase12_core.sql`
- `migrations/postgres/003_phase12_seed_businesses.sql`
- `ntheemba/infrastructure/postgres/businesses.py`

Completion test:

- exact seeded channels resolve to one business before interpretation.

## Goal 3: Per-business capability settings

`business_capabilities` records:

- `business_id`
- `capability_id`
- `enabled`
- `config JSONB`

Only enabled capabilities compile into runtime permissions. Capability config is retained on the `BusinessProfile` for business-specific behavior without using `business_type` branching.

Completion test:

- Harvest has no booking integration.
- Serah has appointment capability config and booking support.

## Goal 4: Business integration registry

`business_integrations` records:

- provider
- adapter type
- deployment/base URL
- API version
- auth reference
- status
- enabled flag
- supported capabilities
- JSON config

The compiled Redis/runtime payload includes routing metadata but excludes `auth_reference` and integration `config`.

Completion test:

- Harvest and Serah resolve different stored TradeFlow integrations.
- Workflows use resolved integration context; workflow code must not contain tenant deployment URLs.

## Goal 5: Compiled business runtime

`RuntimeProfileCompiler` loads the business, channel, enabled capabilities, and usable integrations from the registry, then compiles a `CompiledRuntimeProfile`.

The runtime contains only:

- an enabled business;
- an enabled channel;
- known enabled capabilities;
- enabled integrations whose status is `active` or `testing`;
- integration capabilities already known by the catalogue.

Completion test:

- runtime profile tests pass for Harvest, Serah, stale cache reload, revision invalidation, channel isolation, disabled integration denial, and redacted cache payload.
