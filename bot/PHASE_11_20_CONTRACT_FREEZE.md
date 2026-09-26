# Phase 11.20 — End-to-End Acceptance and Contract Freeze

Phase 11.20 freezes the interfaces that Phase 12 will persist.

Rebaseline note: TradeFlow tenant contract work after the 2026-08-22 source-root reconciliation must use `TRADEFLOW_PUBLIC_CONTRACT_V1.md` and the approved active source roots as the baseline decision record. Do not use `apps/ntheemba/appscript-bridge/Index copy.html` or `apps/ntheemba/appscript-bridge/code copy.gs` to define TradeFlow operations, adapter DTOs, or product workflows.

Frozen contracts:

- canonical Ntheemba capability IDs;
- capability-to-workflow meanings;
- capability-to-TradeFlow operation mappings;
- business/channel resolution;
- provider-neutral inbound and outbound envelopes;
- platform customer versus business-client boundaries;
- business-specific session identity;
- reliable gateway claim/ack/retry semantics;
- multi-conversation simulator diagnostics;
- unsupported capability and method observations.

Acceptance coverage includes:

- Standard TradeFlow product and order conversations;
- AMAC capability denial for delivery;
- Serah client recognition and minimal client creation;
- Serah appointment and product flows;
- loyalty read through TradeFlow;
- same customer across separate businesses;
- exact outgoing channel preservation;
- duplicate message handling;
- unknown capability and method rejection;
- legacy OpenWA session translation;
- reliable queue acknowledgement and retry behavior.

Phase 12 may replace in-memory implementations with Redis and PostgreSQL, but it must not redesign these contracts.
