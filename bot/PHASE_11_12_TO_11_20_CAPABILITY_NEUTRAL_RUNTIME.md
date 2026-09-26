# Ntheemba Phase 11.12–11.20
## Capability-Neutral Multi-Business Runtime

## Governing rule

Ntheemba owns the canonical capability catalogue, definitions, workflow meanings, and TradeFlow operation mappings. Connected businesses only declare support for known capabilities.

Unknown declarations or methods are never auto-enabled. They are rejected, observed, and held for an explicit Ntheemba design and approval process.

## Delivered phases

| Phase | Delivery |
|---|---|
| 11.12 | Closed Ntheemba capability catalogue and capability guard |
| 11.13 | Exact receiving-channel business resolution and tenant isolation |
| 11.14 | Multi-business, multi-conversation simulator workspace |
| 11.15 | Minimal platform customer and private business-client bridge |
| 11.16 | Reusable client, product, service, appointment, loyalty, and handover workflow library plus compound plan model |
| 11.17 | Versioned Ntheemba-owned TradeFlow operation contract and unknown-method observation |
| 11.18 | Standard and Serah reference adapter boundaries |
| 11.19 | Legacy OpenWA envelope translation and reliable queue semantics |
| 11.20 | End-to-end acceptance coverage and pre-Phase-12 contract freeze |

## Runtime pipeline

```text
Provider message
→ exact channel resolution
→ business profile
→ canonical capability validation
→ platform customer resolution
→ optional business-client resolution
→ business-specific session
→ interpretation
→ transition validation
→ capability guard
→ reusable workflow
→ approved TradeFlow operation
→ session commit
→ exact-channel reply
```

## Business examples

### Harvest Big Shop

Standard TradeFlow capabilities include products, orders, delivery, collection, information, FAQs, and handover.

### AMAC Enterprise

Standard TradeFlow capabilities include products, orders, collection, information, FAQs, and handover. Delivery is deliberately disabled to prove runtime capability enforcement.

### Serah's Glow Lounge

The customised TradeFlow profile additionally enables minimal clients, services, appointments, and loyalty. These remain reusable Ntheemba capabilities rather than Serah-specific bot code.

## Unsupported integration review

Developer diagnostics expose observations at:

```text
GET /dev/simulator/workspace/unsupported
```

An observation is evidence only. It never changes the capability catalogue or runtime permissions.

## Developer workspace

```text
http://127.0.0.1:8000/dev/simulator/workspace
```

The workspace keeps independent sessions for multiple customers and businesses, and displays business resolution, capabilities, traces, replies, and session state.

## Phase 12 entry point

Phase 12 will add Redis and PostgreSQL implementations behind the frozen Phase 11 ports:

- Redis sessions, locks, deduplication, idempotency, and gateway streams;
- PostgreSQL platform customers, consent, business-client links, summaries, and observations.

Phase 12 must preserve the Phase 11.20 contracts.
