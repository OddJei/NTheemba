# Ntheemba failures, observability, and safe handover

## Scope

This project makes product resolution operable and diagnosable for Ntheemba with NCPC and TradeFlow adapters. It does not deploy any service and does not prove production runtime behavior.

NCPC remains the shared product identity source. TradeFlow remains the tenant/shop source for public product visibility, price, availability, and customer-changing order or booking actions.

## Product-resolution outcomes

| Outcome | Meaning | Customer behavior | Retry behavior |
|---|---|---|---|
| `NCPC_NO_MATCH` | NCPC has no public canonical match for the query. | Ask the customer to try another name, size, brand, category, or ask for a person. | Safe read retry. |
| `SHOP_NO_MATCH` | NCPC matched identity, but the current shop has no public matching item. | Say the item was not found in this shop's public catalogue. | Safe read retry. |
| `SHOP_MATCHES` | The shop has multiple public candidates. | Show bounded customer-safe options and ask for selection. | Safe read retry. |
| `NCPC_TIMEOUT` | NCPC read did not complete. | Say the catalogue cannot be checked right now. | Safe read retry only; no item is selected. |
| `TRADEFLOW_TIMEOUT` | TradeFlow read did not complete. | Say this shop's product details cannot be checked right now. | Safe read retry only; no item is selected. |
| `AUTH_FAILURE` | Adapter authorization failed. | Ask the customer to speak with a person. | Do not automatic-retry as a customer action. |
| `MALFORMED_RESPONSE` | Adapter data could not be parsed safely. | Ask the customer to speak with a person. | Do not automatic-retry as a customer action. |
| `STALE_SELECTION` | Saved choices expired or no longer match the tenant/customer/conversation scope. | Ask the customer to search again. | Safe read retry from a new search. |
| `SESSION_EXPIRED` | The conversation session is expired. | Ask the customer to send the product request again. | Starts from a fresh session. |

## Observability

Catalogue workflow events use correlation IDs and redacted outcome data:

- `correlation_id`
- `message_id`
- `business_id`
- `conversation_id`
- `flow`
- `outcome`
- `dependency`
- `operation`
- `retryable`
- `safe_to_retry`
- `elapsed_ms`
- bounded counts such as `candidate_count`

Events must not include full customer messages, credentials, tokens, another tenant's prices, raw adapter payloads, or full product lists.

## Retry safety

Product resolution retries are read-only. Timeouts return before candidate state is saved or a product is selected.

Customer-changing actions remain behind confirmation workflows and TradeFlow idempotency keys. A retry must reuse the same idempotency key for the same confirmed action and must not create a second order, booking, or client record.

## Session expiry

Pending product choices have a short TTL and are scoped by business, customer, conversation, and correlation ID. Expired or cross-scope selections are rejected as `STALE_SELECTION` and the customer must search again.

Expired conversation sessions are archived/replaced by the session coordinator. If an expired session reaches catalogue handling directly, the deterministic `SESSION_EXPIRED` response is returned.

## Human handover

Customers can ask for a person from any failure message. Repeated invalid selections and "none of these" also request handover.

Handover events may record whether confirmed context is available. They must not include unresolved candidate lists. Confirmed context exists only after a product, service, order detail, or booking detail has been explicitly selected or confirmed in the active tenant session.

## Evidence boundary

Local unit tests and static checks show deterministic local behavior only. They are not evidence that a deployed Apps Script, gateway, NCPC, or TradeFlow production runtime executed these paths.
