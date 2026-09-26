# Ntheemba Phase 12 — Durable Runtime and Customer Memory

## Foundation

Phase 12 is rebuilt from the Phase 11.20 contract freeze. It does not revive the
older pre-capability branch.

The governing rule remains:

> Ntheemba owns the canonical capabilities, workflow meanings, and TradeFlow
> operations. A TradeFlow business only declares support for identifiers that
> Ntheemba already knows.

PostgreSQL may persist a declaration such as `product.order`, but the database
row has no authority to activate it. `BusinessContextResolver` validates every
loaded declaration through `CapabilityCatalogue.canonical()`. Unknown values are
removed from the resolved capability set, recorded in
`unsupported_declarations`, and never forwarded to a workflow or adapter.

## Runtime ownership

```text
Redis
  active conversation sessions
  archived session snapshots
  distributed locks
  inbound message deduplication
  external-action idempotency
  acknowledged inbound/outbound gateway streams

PostgreSQL
  business and channel registry
  business capability declarations
  unsupported capability/method observations
  minimal platform customers
  private business-client links
  consent records
  saved checkout details
  conversation summaries and question analytics

TradeFlow
  products, services, prices and stock
  orders and appointments
  business-specific client records
  loyalty calculations

Ntheemba
  capability catalogue
  workflow meanings and transitions
  channel/business resolution
  customer conversation orchestration
  consent enforcement
```

## Phase 12.1 — Storage configuration and lifecycle

`StorageRuntime` owns Redis and PostgreSQL clients and opens them through the
FastAPI lifespan. Explicit durable backend selection fails startup when the
required DSN is absent or the service cannot be opened; there is no silent
fallback to memory.

Readiness reports whether configured Redis and PostgreSQL stores are reachable.
The default test/developer profile remains memory-only, while `.env.example`
enables the complete durable profile.

Windows command-line scripts use a selector event loop compatible with Psycopg
async connections. `ntheemba.main` also selects the compatible Windows policy
before the FastAPI app is created.

## Phase 12.2 — Redis session repository

Sessions are encoded with a versioned JSON contract rather than Python pickle.
The repository provides:

- one active key per `business_id + customer_id`;
- optimistic revision checks;
- detached session snapshots;
- seven-day default active TTL refreshed at each successful commit;
- 90-day default archive TTL for completed or expired sessions;
- explicit deletion and archive operations;
- schema validation during decoding.

A session key always includes the business, so one customer can order from
Harvest while separately booking at Serah's Glow.

## Phase 12.3 — Distributed conversation locking

Redis locks use a random owner token, bounded acquisition time, TTL renewal-safe
ownership checks, and owner-only release. Two Ntheemba instances cannot mutate
the same business/customer session simultaneously.

The default lock TTL is 30 seconds. It is deliberately much shorter than the
session TTL because it protects one mutation, not the customer relationship.

## Phase 12.4 — Deduplication and external-action idempotency

Inbound message IDs are claimed per business. Infrastructure failure releases
the claim so the gateway can retry; successfully handled messages remain
claimed for the configured deduplication period.

External writes use a separate idempotency store. The protected operations are:

- client creation and minimal profile update;
- order request creation;
- appointment create, reschedule, and cancellation;
- human handover creation;
- outgoing reply publication.

A completed result is replayed without calling TradeFlow a second time. A
pending result returns an in-progress response. The default idempotency TTL is
30 days.

## Phase 12.5 — Platform customer identity

A platform customer contains only:

- stable Ntheemba customer ID;
- normalized E.164 phone number;
- optional consented preferred name;
- preferred language;
- created and last-seen timestamps;
- active status.

The phone number lets Ntheemba recognize the same person across participating
businesses. Recognition does not expose any business's private activity.

## Phase 12.6 — Private business-client relationships

Each client-enabled business has a separate link:

```text
business_id
platform_customer_id
external_tradeflow_client_id
business_display_name
first_seen_at
last_seen_at
```

Serah's Glow may therefore identify an existing salon client or create a
minimal client while Harvest keeps an unrelated business relationship. Row
level security is forced on tenant-scoped PostgreSQL tables.

## Phase 12.7 — Consent and minimal saved checkout details

Creating a Serah client does not automatically share the customer's name with
Harvest. The name remains on the Serah business-client link unless the customer
grants `cross_business_name` consent.

The supported permissions are:

- `cross_business_name`;
- `saved_checkout`;
- `message_retention`;
- `marketing`.

Addresses and fulfilment preferences are saved only after `saved_checkout`
consent. Business-specific addresses remain scoped to that business. Raw
message text and question details require `message_retention` consent.

## Phase 12.8 — Conversation summaries and question analytics

Small structured summaries are stored after successful workflow processing.
They contain flow, stage, event names, intent, outcome, and reply count—not an
unbounded transcript.

When message-retention consent exists, Ntheemba may also store customer and
assistant messages and business-scoped question analytics. These help a
business understand common questions and unresolved handovers without allowing
another business to read them.

## Phase 12.9 — Retention and privacy

Default retention policy:

```text
active session                 7 days
session archive               90 days
message deduplication          7 days
external idempotency          30 days
conversation messages        180 days
conversation summaries       730 days
customer questions           730 days
unsupported observations     365 days
conversation lock             30 seconds
```

Identity, consent, and business-client links are not Redis-style temporary
records. They remain until status change, withdrawal, or deletion.

PostgreSQL migrations enable and force row-level security for private business
records. Retention cleanup enters an explicit system-maintenance scope; normal
requests cannot use that scope.

## Phase 12.10 — Gateway recovery and multi-instance operation

The provider-neutral gateway uses Redis Streams consumer groups:

```text
HTTP/OpenWA adapter
  -> authenticated inbound envelope
  -> inbound stream
  -> claim by Ntheemba worker
  -> process through exact business channel
  -> acknowledge, retry, or dead-letter
  -> durable outbound stream
  -> exact-channel provider sender
  -> acknowledge, retry, or dead-letter
```

Workers first reclaim stale pending deliveries left by a crashed instance and
then read new entries. Retry creates a new attempt record before acknowledging
the failed delivery. Maximum attempts are configurable.

The inbound API is:

```text
POST /api/v1/gateway/inbound
Authorization: Bearer <NTHEEMBA_GATEWAY_SHARED_SECRET>
```

The envelope carries the exact `channelInstanceId`, recipient number, provider,
customer number, request ID, and message ID. The customer text cannot select or
override the business.

## Business-specific behavior after durability

### Standard TradeFlow

Harvest, AMAC, and future standard businesses typically activate product,
order, delivery/collection, information, FAQ, and handover capabilities.

### Serah's Glow

Serah activates reusable client, product, service, appointment, loyalty,
collection, information, FAQ, and handover capabilities. Loyalty points and
discounts remain calculated by Serah's TradeFlow app; Ntheemba stores only the
minimal client link and explains the approved loyalty result.

The service/client workflows are not hard-coded as “Serah bot” logic. A future
spa, clinic, or other TradeFlow service business can declare the same known
capabilities and reuse the same Ntheemba workflows.

## Local operation

```powershell
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
docker compose -f .\docker-compose.phase12.yml up -d
python scripts\migrate_postgres.py `
  --dsn "postgresql://ntheemba:ntheemba_local_change_me@localhost:5432/ntheemba"
python scripts\validate_storage.py
python -m uvicorn ntheemba.main:app --reload
```

Developer surfaces:

```text
/dev/simulator/workspace
/dev/storage
/ready
/docs
```

The seeded PostgreSQL channels use simulator identities and placeholder phone
numbers. Register the real OpenWA channel IDs and business numbers before a
production connection.
