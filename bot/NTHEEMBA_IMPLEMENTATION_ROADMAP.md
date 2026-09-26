# Ntheemba Neutral Runtime Implementation Roadmap

Status: working implementation roadmap.

This file is the shared source for future Codex chats. Read it before continuing
Ntheemba, NCPC, or TradeFlow integration work.

## Final Objective

Build one neutral Ntheemba conversation runtime where:

- PostgreSQL is the durable source of truth for connected businesses, channels,
  enabled capabilities, capability configuration, integrations, and runtime
  revisions.
- Redis is only the fast runtime/session/cache layer.
- Ntheemba owns capability definitions, workflow semantics, validation, routing,
  and guards.
- Generic workflows are activated only by enabled capabilities.
- Business-specific calls are routed through stored integration records.
- NCPC owns shared product identity.
- TradeFlow owns tenant-specific product visibility, price, stock, services,
  booking, order, and operational truth.
- No hardcoded Harvest bot, Serah bot, grocery bot, salon bot, or business-type
  workflow branching exists.

## Current Baseline

Goals 1-5 are implemented locally and must be treated as a baseline that still
needs safe commit/review evidence:

- versioned Ntheemba capability catalogue;
- PostgreSQL businesses/channels/capabilities/integrations;
- per-business capability `enabled` and `config JSONB`;
- integration metadata for provider, URL, API version, auth reference, status;
- compiled runtime profile loader;
- local tests for runtime profile compilation, capability rejection, disabled
  integrations, cache redaction, and migration shape.

Known limitations:

- local tests do not prove production Apps Script or deployed runtime behavior;
- production reference files are archived inputs only;
- root Git must be staged carefully to avoid committing archives, backups,
  customer documents, zips, local runtime state, or secrets.

## Road 0: Repo And Source Control

Objective: make the root workspace the only active working repo.

Deliverables:

- root workspace tracks `https://github.com/OddJei/NTheemba-Platform.git`;
- no staging clone exists in the root workspace;
- active Ntheemba source root is `apps/ntheemba/bot`;
- production references remain archived and local-only.

Completion tests:

- `git remote -v`;
- `git status --short --branch`;
- root does not contain `repo-staging-ntheemba-platform`.

## Road 1: Freeze Current Baseline

Objective: commit only safe Ntheemba Goals 1-5 baseline work.

Deliverables:

- reviewed staged file list;
- one safe commit containing only source, tests, migrations, and docs needed for
  the Ntheemba baseline.

Completion tests:

- `python -m pytest tests/unit`;
- `python scripts/validate_phase_12.py`;
- staged files exclude archives, backups, Docs customer material, zips, secrets,
  local runtime files, and production references.

## Road 2: Architecture Evidence Pack

Objective: prove what exists before adding more architecture.

Deliverables:

- evidence document for capability catalogue;
- durable business/channel registry evidence;
- per-business capability setting evidence;
- business integration registry evidence;
- compiled runtime evidence;
- gap list for Roads 3-12.

Completion test:

- a reviewer can verify current implementation status without reading the whole
  codebase.

## Road 3: Runtime Configuration Admin Path

Objective: make runtime configuration maintainable without editing seed SQL.

Deliverables:

- controlled registration/update path for businesses, channels, capabilities,
  capability config, integrations, and statuses;
- runtime revision bump whenever relevant config changes;
- tests for enable/disable/update behavior.

Completion test:

- disabling Serah booking increments revision and the next compiled runtime no
  longer exposes booking.

## Road 4: Redis Runtime Cache Finalization

Objective: finish Redis as a redacted fast cache, never the source of truth.

Deliverables:

- revisioned runtime cache;
- stale cache invalidation;
- Redis miss reload from PostgreSQL;
- redacted payload rules.

Completion tests:

- Redis loss rebuilds runtime from PostgreSQL;
- capability or integration changes invalidate stale runtime;
- cached payload excludes secrets, auth references, private config, phone
  numbers, and tenant-private operational data.

## Road 5: Integration-Aware Guard

Objective: block every unavailable or unsafe operation before any external call.

Guard must verify:

- known capability;
- globally supported capability;
- business-enabled capability;
- configured enabled integration;
- supported operation;
- valid workflow transition;
- required inputs.

Completion tests:

- Harvest booking is denied with no TradeFlow API call;
- Serah booking is allowed only through Serah's configured integration;
- unknown capability or operation is recorded and cannot run.

## Road 6: Common Dynamic TradeFlow Adapter

Objective: use one Ntheemba-facing adapter contract bound dynamically to the
business integration.

Deliverables:

- common operation contract for information, catalogue, availability, order,
  services, booking, and handover;
- dynamic integration resolver;
- safe optional-operation failures;
- no tenant URLs in workflow code.

Completion tests:

- Harvest never calls Serah's URL;
- Serah never calls Harvest's URL;
- unsupported optional operations fail safely.

## Road 7: Capability-Aware Interpreter

Objective: only expose allowed business actions to interpretation.

Deliverables:

- allowed-action context from compiled runtime profile;
- validator rejection of unavailable model-proposed actions;
- no business-type bot classes.

Completion tests:

- Harvest allowed actions exclude booking;
- Serah allowed actions include booking;
- model-proposed unavailable action is rejected;
- no `HarvestBot`, `SalonBot`, or business-type workflow branching exists.

## Road 8: Generic Workflow Completion

Objective: keep workflows reusable and capability-driven.

Deliverables:

- generic information workflow;
- generic catalogue workflow;
- generic order workflow;
- generic booking workflow;
- generic handover workflow.

Completion test:

- the same booking workflow works for any business with booking capabilities and
  fails for businesses without those capabilities.

## Road 9: NCPC Product Resolution

Objective: complete customer-confirmed NCPC to TradeFlow product resolution.

Required flow:

```text
customer wording
-> NCPC identity candidates
-> TradeFlow business-specific filtering, price, and availability
-> customer confirms one choice
-> session stores exact TradeFlow item and NCPC IDs
```

Completion tests:

- exact barcode;
- typo or alias;
- size warning;
- NCPC no match;
- shop no match;
- multiple matches;
- "number 2" selection;
- stale selection;
- two-business isolation.

## Road 10: Reliability, Privacy, Observability

Objective: make the runtime operable and safe.

Deliverables:

- redacted structured events;
- correlation/request IDs;
- dedupe;
- idempotency;
- tenant-scoped sessions;
- safe retries;
- human handover;
- failure recovery.

Completion tests:

- repeated messages do not duplicate business-changing actions;
- logs contain no secrets or tenant-private payloads;
- failed authoritative calls recover safely.

## Road 11: Local Two-Business Proof

Objective: prove the neutral runtime with Harvest and Serah.

Deliverables:

- local evidence report showing Harvest and Serah behavior;
- command output or test results;
- cross-business isolation proof.

Completion tests:

- Harvest catalogue/order allowed;
- Harvest booking denied with no API call;
- Serah catalogue/services/booking allowed;
- Redis reload works;
- no cross-business URL, cache, or session leakage.

## Road 12: Independent Gate And Test Deployment Readiness

Objective: decide whether the implementation is ready for test deployment.

Deliverables:

- independent security review;
- independent reality review;
- release checklist;
- rollback plan;
- test environment config checklist;
- residual risk list.

Completion test:

- no Critical or High tenant, secret, auth, source-root, or deployment issue
  remains.

## Required Order

1. Road 0: repo/source control sanity.
2. Road 1: freeze current baseline.
3. Road 2: evidence pack.
4. Road 3: runtime configuration admin path.
5. Road 4: Redis runtime cache finalization.
6. Road 5: integration-aware guard.
7. Road 6: common dynamic TradeFlow adapter.
8. Road 7: capability-aware interpreter.
9. Road 8: generic workflow completion.
10. Road 9: NCPC product resolution.
11. Road 10: reliability, privacy, observability.
12. Road 11: local two-business proof.
13. Road 12: independent gate and test deployment readiness.

## Global Stop Conditions

Stop before implementation if any of these appear:

- unclear tenant or business identity;
- unclear trusted-data authority;
- need to deploy Apps Script or modify a production Sheet;
- production credential or secret exposure;
- need to copy tenant code/data into another tenant;
- destructive migration;
- Critical or High security finding.

## Global Non-Goals

Do not:

- build separate business-type bots;
- hardcode tenant Apps Script URLs inside workflows;
- let Redis become the configuration source of truth;
- let the LLM decide business capability support;
- expose every capability to every business;
- expose tenant-private TradeFlow data through NCPC or logs;
- treat local tests as production deployment proof.
