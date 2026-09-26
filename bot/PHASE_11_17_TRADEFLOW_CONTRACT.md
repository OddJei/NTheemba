# Phase 11.17 — Ntheemba-Owned TradeFlow Contract

Ntheemba owns a closed catalogue of TradeFlow operations in `TradeFlowOperation`.

The shared public DTO and edition-support baseline is `TRADEFLOW_PUBLIC_CONTRACT_V1.md`.

## Reconciled TradeFlow baseline

As of the 2026-08-22 source-root reconciliation, Ntheemba-facing TradeFlow tenant contracts must be derived from active TradeFlow and NCPC source roots, not from copied files under the Ntheemba bridge.

Approved baseline inputs:

- Standard TradeFlow contract additions: `apps/tradeflow/standard/appscript/NtheembaMapping.gs` with `apps/tradeflow/standard/appscript/code copy.gs` and `apps/tradeflow/standard/appscript/Index copy.html`.
- Serah's Glow custom tenant behavior: `apps/tradeflow/customised/serahs-glow/appscript/Code.gs` and `apps/tradeflow/customised/serahs-glow/appscript/index.html`.
- Harvest custom tenant behavior: `apps/tradeflow/customised/harvest-app/appscript/Code.gs` and `apps/tradeflow/customised/harvest-app/appscript/index.html`.
- NCPC recognition and candidate search: `apps/central-catalogue/Apps Script/Code.gs` and the `ncpc-candidate-search-v1` contract.
- Bridge-only contract material: `apps/ntheemba/appscript-bridge/Ntheemba.gs`.

`apps/ntheemba/appscript-bridge/Index copy.html` and `apps/ntheemba/appscript-bridge/code copy.gs` are excluded from baseline use. They are deprecated embedded TradeFlow copies and must not define Ntheemba operations, adapter DTOs, or product workflows.

Every request is:

- versioned;
- tenant-bound;
- correlated by request ID;
- mapped to exactly one canonical capability;
- optionally protected by an idempotency key.

## Unknown method rule

When TradeFlow proposes or invokes a method not known by Ntheemba:

1. parsing fails before a typed request is created;
2. the method is not sent to an adapter;
3. Ntheemba returns `UNKNOWN_TRADEFLOW_OPERATION`;
4. an unsupported-operation observation is recorded;
5. no capability is created or enabled.

A known method for a capability not enabled by the business returns `CAPABILITY_NOT_ENABLED` and is also observed.

Main implementation:

- `ntheemba/domain/tradeflow_contract.py`
- `ntheemba/ports/tradeflow_contract.py`
- `ntheemba/adapters/tradeflow/contract.py`
