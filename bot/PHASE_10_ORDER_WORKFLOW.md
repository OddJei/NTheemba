# Phase 10 — Order Workflow

Phase 10 implements a complete, production-shaped product-order request flow.
It builds on the Phase 9 catalogue workflow and submits only after a fresh
TradeFlow stock and price check.

## Added files

```text
ntheemba/workflows/
└── order.py

tests/unit/workflows/
└── test_order.py

tests/unit/application/
└── test_order_integration.py
```

Phase 10 also strengthens:

```text
ntheemba/domain/order_draft.py
ntheemba/domain/transitions.py
ntheemba/services/interpretation.py
ntheemba/services/product_resolver.py
ntheemba/services/response_builder.py
ntheemba/workflows/catalogue.py
```

## Routed intents

`build_order_routes()` registers:

- `START_ORDER`
- `PROVIDE_QUANTITY`
- `PROVIDE_FULFILMENT_METHOD`
- `PROVIDE_DELIVERY_DETAILS`
- `PROVIDE_CUSTOMER_DETAILS`
- `CONFIRM`
- `CORRECT`
- `CANCEL`

The catalogue workflow continues to own `CATALOGUE_SEARCH` and `SELECT_ITEM`,
including when the owning flow is `ORDER`.

## Main flow

```text
IDLE / START
    ↓ START_ORDER
ORDER / CATALOGUE_SEARCH
    ↓ NCPC + TradeFlow product resolution
ORDER / PRODUCT_SELECTED
    ↓ quantity
ORDER / QUANTITY
    ↓ live quantity and price check
ORDER / FULFILMENT_METHOD
    ├── collection → CUSTOMER_DETAILS
    └── delivery   → DELIVERY_DETAILS → CUSTOMER_DETAILS
    ↓
ORDER / ORDER_REVIEW
    ↓ fresh confirmation-time stock and price check
ORDER / SUBMITTING
    ↓ idempotent TradeFlow create_order_request
ORDER / SUBMITTED
```

## Starting from a catalogue product

A customer can first browse normally and then say `order this`.

```text
CATALOGUE / PRODUCT_SELECTED
    ↓ START_ORDER
Create OrderDraft with saved resolved product
    ↓
ORDER / QUANTITY
```

## Starting with product language

A customer can begin directly:

```text
Customer: order Boom 500g
```

The order workflow enters `ORDER / CATALOGUE_SEARCH` and delegates product
identity resolution to the Phase 9 catalogue workflow. Exact matches continue
to quantity; ambiguous matches preserve candidates and ask for a selection.

A combined message is also supported:

```text
Customer: order 2 Boom 500g
```

The interpreter now distinguishes the order quantity `2` from the product size
`500g`. Product sizes, barcodes, dates, times, and phone numbers are excluded
from quantity extraction.

## Order draft guarantees

`OrderDraft` now owns:

- selected resolved product;
- quantity;
- fulfilment method;
- delivery details;
- customer name and contact;
- accepted price snapshot;
- availability validation state;
- stable idempotency key;
- submitted TradeFlow request ID and status.

Changing any order field automatically invalidates the prior stock, price, and
submission state.

## Stock and price checks

The workflow checks TradeFlow at three important points:

1. after quantity entry;
2. before showing the final review;
3. immediately before submission.

If the requested quantity is no longer available, the customer returns to the
quantity stage. If the product is no longer public, the customer returns to the
product search stage.

## Price-change protection

A price change is never silently accepted.

```text
Customer confirms order at K24.00
    ↓
TradeFlow now reports K25.00
    ↓
Update draft price
Show revised review
Require another CONFIRM
```

Only the next confirmation can submit the updated order.

## Idempotent submission

Each new `OrderDraft` receives one stable internal idempotency key. TradeFlow is
called with that key, so repeated processing cannot create a second request.

After successful submission, the draft stores the public request ID and status.
If the confirmation message is retried after an outgoing publisher failure,
Ntheemba can replay the same success response without calling TradeFlow again.

## Corrections

Before submission, the customer may correct:

- product;
- quantity;
- fulfilment method;
- delivery details;
- customer name or contact.

Unchanged fields remain in the draft. Correcting any field invalidates the old
validation snapshot and returns the session to the appropriate collection
stage.

## Cancellation

`CANCEL` clears:

- order draft;
- product resolution;
- pending question;
- suspended state;
- clarification count.

The session moves to `IDLE / CANCELLED`.

## Customer-safe output

The order review contains public details only:

```text
Review your order request:
Product: Boom Washing Powder 500g
Quantity: 2
Fulfilment: delivery
Delivery: House 12 near the blue water tank
Unit price: K24.00
Estimated total: K48.00
Name: James Chisulo
Contact: 0970000000
Reply CONFIRM to submit, CORRECT to change something, or CANCEL.
```

NCPC IDs, business-product IDs, validation references, and idempotency keys are
never included in outgoing messages.

## Full integration test

The application integration test processes:

```text
1. order Boom 500g
2. two
3. delivery
4. House 12 near the blue water tank
5. James Chisulo 0970000000
6. confirm
```

It verifies:

- every message is processed;
- word quantity `two` becomes `2`;
- product resolution uses NCPC and TradeFlow;
- the final price is K48.00;
- one TradeFlow order is created;
- the session reaches `ORDER / SUBMITTED`;
- no internal product IDs appear in replies;
- the reply states that no payment was taken.

## Run checks

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy ntheemba tests
```

## Next phase

Phase 11 implements service booking:

```text
ntheemba/workflows/
└── booking.py
```

It will cover service selection, preferred date, available slots, optional
staff selection, customer details, live slot revalidation, correction,
confirmation, and idempotent TradeFlow booking submission.
