# Ntheemba-Facing TradeFlow Public Contract V1

Status: SPECIFICATION BASELINE - not a deployment approval
Schema version: `tradeflow.ntheemba.v1`
Batch NCPC lookup version: `tradeflow.ntheemba.find_items_by_ncpc_variants.v1`
Date: 2026-08-22

## Authority And Baseline

This contract is derived from the approved active source roots below. It does not include archived inputs, production deployment records, credentials, or tenant runtime data.

Use these active roots only:

- Standard TradeFlow: `apps/tradeflow/standard/appscript/code copy.gs`, `apps/tradeflow/standard/appscript/Index copy.html`, `apps/tradeflow/standard/appscript/NtheembaMapping.gs`.
- Harvest TradeFlow: `apps/tradeflow/customised/harvest-app/appscript/Code.gs`, `apps/tradeflow/customised/harvest-app/appscript/index.html`.
- Serah's Glow TradeFlow: `apps/tradeflow/customised/serahs-glow/appscript/Code.gs`, `apps/tradeflow/customised/serahs-glow/appscript/index.html`.
- NCPC: `apps/central-catalogue/Apps Script/Code.gs` and `ncpc-candidate-search-v1`.
- Bridge-only source: `apps/ntheemba/appscript-bridge/Ntheemba.gs`.

Do not use `apps/ntheemba/appscript-bridge/Index copy.html` or `apps/ntheemba/appscript-bridge/code copy.gs` as TradeFlow baselines.

## Contract Principles

- Ntheemba owns the closed operation catalogue in `ntheemba/domain/tradeflow_contract.py`.
- TradeFlow owns tenant-local product, service, price, availability, order, booking, stock, policy, and business records.
- NCPC owns shared product identity, variants, identifiers, aliases, evidence, release state, and candidate search.
- Every request is tenant-bound by `business_id`, versioned, correlated by `request_id`, and checked against the business's enabled Ntheemba capability.
- Write operations require an idempotency key and must be implemented with the tenant deployment's lock/concurrency mechanism.
- Responses are public DTOs only. They must not expose costs, suppliers, batches, stock quantities unless explicitly allowed below, private notes, payroll, private staff/customer records, credentials, deployment IDs, full app state, or source rows.

## Capability Matrix

Legend: `Core` means this is part of the common public contract when the edition declares the capability. `Optional` means edition-specific support requiring that edition's active-root adapter. `No` means the edition must reject the operation unless a new reviewed adapter spec approves it.

| Capability | Operations | Standard | Harvest | Serah's Glow | Authority owner |
| --- | --- | --- | --- | --- | --- |
| Business information | `business.get_profile` | Core | Core | Core | TradeFlow tenant |
| Business hours | `business.get_hours` | Core | Core | Core | TradeFlow tenant |
| FAQ | `faq.search` | Core | Core | Core | TradeFlow tenant |
| Product catalogue | `catalogue.search_products`, `catalogue.get_product`, `inventory.get_public_availability` | Core | Core | Core | NCPC identity + TradeFlow tenant price/availability |
| Product order | `order.validate`, `order.create_request`, `order.get_request_status` | Core | Optional | Optional | TradeFlow tenant |
| Delivery | `fulfilment.validate_delivery` | Optional | Optional | Optional | TradeFlow tenant policy |
| Collection | `fulfilment.validate_collection` | Optional | Optional | Optional | TradeFlow tenant policy |
| Client identify | `client.find_by_phone`, `client.get_minimal_profile` | No | Optional | Optional | TradeFlow tenant |
| Client create | `client.create`, `client.update_minimal_profile` | No | Optional | Optional | TradeFlow tenant |
| Service catalogue | `catalogue.search_services`, `catalogue.get_service` | No | Optional | Core | TradeFlow tenant |
| Appointment create | `appointment.check_availability`, `appointment.get_alternatives`, `appointment.create_request` | No | Optional | Core | TradeFlow tenant |
| Appointment reschedule | `appointment.reschedule_request` | No | Optional | Optional | TradeFlow tenant |
| Appointment cancel | `appointment.cancel_request` | No | Optional | Optional | TradeFlow tenant |
| Loyalty read | `loyalty.get_status`, `loyalty.get_progress` | No | No unless separately specified | Core | TradeFlow tenant |
| Handover | `handover.create_request` | Core | Core | Core | TradeFlow tenant + Ntheemba |

## Operation Schemas

All responses include:

```json
{
  "request_id": "REQ-...",
  "business_id": "tenant-business-id",
  "schema_version": "tradeflow.ntheemba.v1",
  "ok": true,
  "data": {}
}
```

Failures include `ok=false`, stable `error_code`, and a customer-safe `error_message`.

| Operation | Request payload | Safe response data | Notes |
| --- | --- | --- | --- |
| `business.get_profile` | `{}` | `business_id`, `name`, `description`, `location`, `contact_phone`, `currency`, optional `categories`, `fulfilment_methods`, `handover_enabled` | No owner email, deployment URL, Sheet ID, internal settings, or credentials. |
| `business.get_hours` | `at` ISO timestamp | `timezone`, `checked_at`, `date`, `day`, `is_open`, `opens_at`, `closes_at`, `special_closure`, `note` | Business timezone comes from tenant config or Apps Script timezone. |
| `faq.search` | `query`, optional `limit` | list of `faq_id`, `question`, `answer`, `score` | Only owner-approved public FAQ rows. |
| `catalogue.search_products` | `query`, optional `category`, `limit`, or NCPC candidates | list of public product DTOs | Standard product lookup must use NCPC candidate search plus secured batch filtering when resolving NCPC variants. |
| `catalogue.get_product` | `business_product_id` | one public product DTO or safe not-found | Re-read from TradeFlow before customer confirmation or order submission. |
| `inventory.get_public_availability` | `business_product_id`, `quantity` | `business_product_id`, `requested_quantity`, `available`, `selling_price`, `currency`, `stock_status` | Do not return raw stock quantity unless an edition-specific adapter has explicit public approval. |
| `order.validate` | product, quantity, fulfilment, customer contact draft | `valid`, `warnings`, `total_estimate`, `currency`, `fulfilment_method` | Validation only; no stock mutation. |
| `order.create_request` | validated product order with customer confirmation and `idempotency_key` | `request_id`, `request_type="order"`, `status`, `created` | Creates a request/lead, not a POS sale or automatic stock deduction. |
| `order.get_request_status` | `request_id` | `request_id`, `request_type`, `status`, `updated_at` | Tenant-local request only. |
| `fulfilment.validate_delivery` | delivery area/address/contact draft | `valid`, `reason`, `fee_estimate`, `currency` | Tenant policy owned by TradeFlow. |
| `fulfilment.validate_collection` | optional pickup location/time draft | `valid`, `location`, `instructions` | Tenant policy owned by TradeFlow. |
| `client.find_by_phone` | normalized `phone_e164` | minimal `client_id`, `display_name`, allowed contact flags | No full customer profile, notes, history, balances, payroll, or private metadata. |
| `client.get_minimal_profile` | `client_id` | minimal `client_id`, `display_name`, public appointment/order context if approved | Tenant-scoped only. |
| `client.create` | confirmed `display_name`, `phone_e164`, `idempotency_key` | minimal `client_id`, `display_name`, `created` | Supports known, named walk-in, or manually captured service paths only where the tenant app supports them. |
| `client.update_minimal_profile` | `client_id`, minimal confirmed updates, `idempotency_key` | minimal `client_id`, `updated` | No private notes or financial fields. |
| `catalogue.search_services` | `query`, optional `category`, `limit` | service list with `service_id`, `name`, `description`, `category`, `duration_minutes`, `public_price`, `currency` | Serah has active service workflows; Harvest requires its own adapter spec before enablement. |
| `catalogue.get_service` | `service_id` | one service DTO | Must omit staff wage/share, internal service tags unless public, and private settings. |
| `appointment.check_availability` | `service_id`, `date`, optional `staff_id`, optional customer scope | `available`, `slot`, `alternatives`, `reason` | Must use tenant app's conflict, buffer, staff qualification, and shop rules. |
| `appointment.get_alternatives` | `service_id`, `date`, optional `after`, optional `staff_id` | list of public slots | No staff private calendars or payroll fields. |
| `appointment.create_request` | confirmed booking draft and `idempotency_key` | `request_id`, `request_type="booking"`, `status`, `created` | Must revalidate under lock before reserving/requesting a slot. |
| `appointment.reschedule_request` | existing request/customer proof, new slot, `idempotency_key` | `request_id`, `status`, `created` | Optional until tenant adapter implements it. |
| `appointment.cancel_request` | existing request/customer proof, reason, `idempotency_key` | `request_id`, `status`, `created` | Optional until tenant adapter implements it. |
| `loyalty.get_status` | `client_id` or customer proof | public loyalty tier/status, points/progress summary, next reward | Serah-owned calculation; Ntheemba must not recalculate from private sales/payroll data. |
| `loyalty.get_progress` | `client_id` or customer proof | public progress details and customer-safe explanation | Serah-owned calculation. |
| `handover.create_request` | conversation/customer summary, urgency, `idempotency_key` | `request_id`, `status`, `handover_channel` | Must redact sensitive trace/tool data. |

## Public Product DTO

```json
{
  "business_product_id": "LOCAL-PRODUCT-ID",
  "ncpc_product_id": "PRD-...",
  "ncpc_variant_id": "VAR-...",
  "display_name": "Customer-safe item name",
  "description": "",
  "public_price": 0,
  "currency": "ZMW",
  "availability": "available",
  "stock_status": "in_stock",
  "image_url": "",
  "contract_version": "tradeflow.ntheemba.v1"
}
```

Allowed availability values: `available`, `unavailable`, `limited`, `unknown`.
Allowed stock status values: `in_stock`, `out_of_stock`, `limited`, `unknown`.

## Secured Batch NCPC-Variant Filtering

Standard product lookup uses NCPC to find candidate `VAR-*` identifiers, then calls the tenant TradeFlow deployment to filter those candidates to products that business actually sells and has marked public.

Action: `find_items_by_ncpc_variants`

Request requirements:

- `contract_version` must equal `tradeflow.ntheemba.find_items_by_ncpc_variants.v1`.
- `api_token` must match the tenant deployment's `NTHEEMBA_API_TOKEN`.
- `business_id` must match the tenant deployment's configured `NTHEEMBA_BUSINESS_ID`.
- `request_timestamp` is Unix milliseconds and must be within five minutes of server time.
- `request_nonce` is one-time, 16-128 URL-safe characters, and consumed under lock.
- `request_signature` is Base64 HMAC-SHA-256 over contract version, business ID, timestamp, nonce, and comma-joined ordered variant IDs separated by newlines, using `NTHEEMBA_API_SIGNING_SECRET`.
- `data.ncpc_variant_ids` must contain 1-50 unique `VAR-*` IDs.

Safe response:

- includes only mapped products where `publicForNtheemba === true`;
- returns business item id, NCPC ids, display name, public price, availability, stock status, and contract version;
- omits costs, suppliers, batches, raw stock quantity, notes, customers, tokens, nonces, and full app state;
- records redacted audit metadata only: request id, time, action, outcome, candidate count, and result count.

Rejected requests must fail closed with a safe error for wrong token, wrong business, invalid/missing signature, stale timestamp, replayed nonce, malformed JSON, invalid/duplicate IDs, empty batches, oversized batches, and missing configuration.

## Edition Support Rules

### Standard

Standard supports the common public business, FAQ, product catalogue, product availability, order request, fulfilment, and handover capabilities. It must reject service, appointment, client, and loyalty operations unless a future active Standard source change implements those workflows and passes requirements/security review.

### Harvest

Harvest is an active custom TradeFlow tenant root with inventory, multishop, role/shop isolation, and restock workflows. It may support common business, FAQ, product catalogue, availability, order request, fulfilment, and handover operations only through a Harvest-specific adapter that preserves shop context and does not expose staff/cost/finance/private data. Service, appointment, client, and loyalty operations are not approved by this shared contract unless a Harvest requirements review identifies active tenant support.

### Serah's Glow

Serah's Glow supports the common public product/business operations and has active service, appointment, client, and loyalty workflows. Its adapter may expose those optional operations only through public DTOs and must preserve Serah-specific service rules, appointment conflict/buffer/staff qualification behavior, loyalty calculation ownership, checkout/service rules, and private customer/staff/payroll protections.

## Two-Business Isolation And Unauthorized-Request Tests

Required test specifications before implementation or deployment:

1. Two businesses with the same NCPC variant must return different tenant-local `business_product_id`, price, and availability from each tenant deployment.
2. A request signed for Business A must fail against Business B's deployment, even when the same `VAR-*` ID exists in both businesses.
3. Business B must not see Business A products, services, pending candidates, customer records, appointments, request statuses, audit rows, or handover records.
4. Wrong token, wrong business ID, invalid signature, stale timestamp, replayed nonce, duplicate variant IDs, malformed JSON, and oversized batches must all return safe failures.
5. Private fields must be absent from every success and failure response: costs, suppliers, batches, stock quantity unless explicitly public, payroll, private notes, full customer records, Sheet IDs, deployment URLs, tokens, nonces, stack traces, and unrestricted app state.
6. Write operations must require idempotency keys and replay the completed result or return in-progress status without creating duplicate tenant records.
7. Appointment booking tests must prove the tenant app revalidates slot availability under lock and rejects stale selected slots.
8. Handover tests must prove conversation summaries are redacted and tenant-scoped.

## Open Gates

- This contract does not approve production deployment.
- Live Apps Script HTTP serialization, script permissions, real Sheet schema, web-app access, webhook delivery, and tenant configuration must be tested in an authorized non-production environment.
- Security/Reality review remains required before any tenant enables new Ntheemba-facing write operations.
