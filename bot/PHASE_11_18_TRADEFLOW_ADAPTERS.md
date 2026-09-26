# Phase 11.18 — Standard and Serah TradeFlow Adapter Boundaries

Two reference adapter boundaries implement the same Ntheemba contract:

Adapter implementations must satisfy `TRADEFLOW_PUBLIC_CONTRACT_V1.md`.

## Reconciled baseline

Adapter behavior must be re-baselined from the approved active source roots.

Do not use `apps/ntheemba/appscript-bridge/Index copy.html` or `apps/ntheemba/appscript-bridge/code copy.gs` as adapter baselines. Those files are deprecated embedded TradeFlow copies and still carry workflows that are not approved for active standard TradeFlow or new Ntheemba integration paths.

## Standard TradeFlow

Supports the standard public business, FAQ, product, order, delivery/collection, and handover operation families.

Baseline source roots: `apps/tradeflow/standard/appscript/code copy.gs`, `apps/tradeflow/standard/appscript/Index copy.html`, and `apps/tradeflow/standard/appscript/NtheembaMapping.gs`.

## Serah's customised TradeFlow

May additionally support minimal clients, services, appointments, and loyalty.

Baseline source root: `apps/tradeflow/customised/serahs-glow/appscript/`.

## Harvest customised TradeFlow

Harvest is an active custom TradeFlow source root at `apps/tradeflow/customised/harvest-app/appscript/`. It is not automatically covered by the Standard or Serah adapter behavior. Any Harvest-facing Ntheemba adapter must be specified and reviewed against that tenant root before implementation.

The adapters do not change Ntheemba workflow meanings. They translate each application's internal model into Ntheemba-approved public DTOs.

The standard adapter rejects service, appointment, and loyalty handlers at construction time. The capability-controlled wrapper also checks the exact resolved business and enabled capability before every call.

This phase supplies the Ntheemba-side adapter contract and deterministic reference adapters. It does not modify or deploy either Apps Script application.

Main implementation:

- `ntheemba/adapters/tradeflow/reference.py`
- `ntheemba/adapters/tradeflow/contract.py`
