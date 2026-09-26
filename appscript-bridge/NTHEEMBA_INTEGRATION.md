# Ntheemba Apps Script bridge contract

This bridge is not a TradeFlow product baseline. It documents the protected Apps Script contract Ntheemba can call after a tenant has an approved TradeFlow deployment.

Reconciled baseline source: `audits/production-reference-reconciliation-2026-08-22.md`.

## Active source baseline

TradeFlow tenant contracts must be based on the reconciled active source roots:

- Standard TradeFlow: `apps/tradeflow/standard/appscript/code copy.gs`, `apps/tradeflow/standard/appscript/Index copy.html`, and `apps/tradeflow/standard/appscript/NtheembaMapping.gs`.
- Serah's Glow custom TradeFlow: `apps/tradeflow/customised/serahs-glow/appscript/Code.gs` and `apps/tradeflow/customised/serahs-glow/appscript/index.html`.
- Harvest custom TradeFlow: `apps/tradeflow/customised/harvest-app/appscript/Code.gs` and `apps/tradeflow/customised/harvest-app/appscript/index.html`.
- NCPC candidate and release contracts: `apps/central-catalogue/Apps Script/Code.gs` and its documented `ncpc-candidate-search-v1` contract.
- Ntheemba bridge contract only: `apps/ntheemba/appscript-bridge/Ntheemba.gs`.

Do not use `apps/ntheemba/appscript-bridge/Index copy.html` or `apps/ntheemba/appscript-bridge/code copy.gs` as a TradeFlow baseline. They are deprecated embedded copies, not active product source roots.

The existing TradeFlow UI and internal workflows remain unchanged. Ntheemba uses separate, protected `doPost` integration APIs owned by the approved TradeFlow tenant deployment or by `Ntheemba.gs` when a bridge-specific contract is intentionally used.

## Script Properties

Set these values in the Apps Script project settings:

- `NTHEEMBA_BUSINESS_ID`: the platform business ID assigned to this TradeFlow copy.
- `NTHEEMBA_API_TOKEN`: a unique random secret containing at least 32 characters. Store the same secret in the Ntheemba business registry.

Run `setupNtheembaIntegration()` once from the Apps Script editor. It validates the properties and creates the integration sheets.

## Integration sheets

- `NtheembaConfig`: approved public business information, weekly hours, special closures, fulfilment methods, and handover settings.
- `NtheembaFAQs`: owner-approved FAQ answers. Only rows with `Public` enabled are returned.
- `NtheembaCatalogue`: explicit public allowlist for products and services. Internal TradeFlow products are invisible until a row with `Public` enabled exists here.
- `NtheembaAvailability`: appointment slots Ntheemba may offer.
- `NtheembaOrderRequests` and `NtheembaBookingRequests`: customer requests created only after validation and confirmation.
- `NtheembaAudit`: redacted integration events.

JSON-valued configuration keys such as `weekly_hours`, `special_closures`, `public_categories`, and `fulfilment_methods` are stored as JSON in the `Value` column.

## Request contract

All calls use HTTP `POST` with JSON. Tokens are sent in the body because query-string secrets can leak into logs.

```json
{
  "api_token": "business-specific-secret",
  "business_id": "BUS001",
  "request_id": "REQ001",
  "customer_id": "26097xxxxxxx",
  "idempotency_key": "BUS001:26097xxxxxxx:message-id:action",
  "action": "search_catalogue",
  "data": { "query": "blue shirt", "item_type": "product" }
}
```

Supported actions are `health`, `business_info`, `business_hours`, `search_faqs`, `search_catalogue`, `get_item`, `product_availability`, `available_slots`, `validate_booking`, `create_order_request`, `create_booking_request`, `request_status`, and `audit_event`.

The API builds explicit public response objects. It never returns supplier data, costs, margins, payroll, private staff records, internal reports, credentials, or unrestricted app state. Order and booking creation require idempotency keys; booking creation revalidates and reserves the slot under a script lock.
