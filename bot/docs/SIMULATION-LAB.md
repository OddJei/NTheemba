# Ntheemba Simulation Lab

`/dev/simulation-lab` is a protected development-only test surface for the
transport-neutral Ntheemba path. It is not an operator screen, gateway,
production diagnostic tool, or customer messaging interface.

## Modes

- **Deterministic simulation** is the default. It submits a text envelope to
  the real `/api/v2/transport/inbound` boundary while existing developer fake
  dependencies provide repeatable workflow fault control.
- **Local end-to-end** is unavailable until local Redis, PostgreSQL, and a
  verified non-production TradeFlow integration are present. It is intended to
  observe the worker, NCPC/TradeFlow calls, and outbound queue processing.

## Authority and safety

The tester supplies only gateway ID, external session ID, sender identity,
recipient identity, text, and bounded metadata. The lab never accepts a
business, shop, capability, scope, or workflow-authority value. The server
uses the protected configured gateway token and Ntheemba resolves the exact
durable binding. Browser output is redacted and never includes gateway tokens.

The Scenario, Node path, and Delivery evidence views retain correlation-scoped
queue/audit evidence. Safe ingress faults can demonstrate credential, replay,
and binding rejection. Gateway claim/ack remains owned by the transport
boundary; the lab observes its evidence but cannot mutate arbitrary deliveries.
Existing `/dev/dependencies` controls remain the only deterministic dependency
fault mechanism.

## Operations and rollback

The lab is registered only for development/test with developer tooling enabled
and uses no persistent lab state. To roll back, remove the router registration
from `ntheemba/main.py`; no migration, business activation, gateway credential,
or customer channel change is involved. Local results never prove real gateway,
provider, deployed TradeFlow, or customer-delivery behavior.
