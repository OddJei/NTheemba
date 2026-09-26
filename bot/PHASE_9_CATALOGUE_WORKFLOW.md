# Phase 9 — Product Catalogue Workflow

Phase 9 connects interpretation, product resolution, session state, TradeFlow
live product facts, and the central response builder.

## Added files

```text
ntheemba/workflows/
└── catalogue.py

tests/unit/workflows/
└── test_catalogue.py

tests/unit/application/
└── test_catalogue_integration.py
```

## Routed intents

`build_catalogue_routes()` registers:

- `CATALOGUE_SEARCH`
- `SELECT_ITEM`

## Search flow

```text
IDLE / START
    ↓ CATALOGUE_SEARCH
CATALOGUE / CATALOGUE_SEARCH
    ↓
ProductResolver
    ├── NO_MATCH → stay ready for another search
    ├── ONE_MATCH → ask for confirmation
    ├── NEEDS_CLARIFICATION → numbered options
    └── customer selection → live TradeFlow detail and image
```

The same handler can operate inside `ORDER / CATALOGUE_SEARCH`. It preserves
`Flow.ORDER` while using the catalogue stages, allowing Phase 10 to reuse the
same product search and selection logic.

## Session state

Pending candidate state is stored in `Session.product_resolution` and scoped to
the business, customer, and conversation. It contains the original query,
candidate order, TradeFlow item ID, NCPC product ID, NCPC variant ID, catalogue
version, expiry, and correlation ID.

When customer input is required, the session also stores a `PendingQuestion`
with:

- expected `SELECT_ITEM` intent;
- customer-safe option labels;
- whether `YES` may confirm the only pending candidate.

This means safe FAQ or opening-hours interruptions and human handover can
preserve and later restore the exact catalogue question.

## Customer selection

The workflow accepts resolver-supported choices:

- one-based option number;
- product name;
- unique size such as `500g`;
- `YES` only for one-match confirmation.

The interpreter recognizes affirmative selection only when the pending question
explicitly sets `allow_confirmation=true`. A simple numbered follow-up such as
`2` resolves inside the saved pending set and must not trigger another NCPC
search. A clearly new product search replaces the old candidate set.

## Product details and images

After customer selection, the workflow persists only the selected
`businessId`, TradeFlow item ID, NCPC product ID, and NCPC variant ID, clears
the pending candidates, then retrieves the current TradeFlow business product
before replying. This ensures:

- current public visibility;
- current price;
- current availability;
- current public image URL.

A removed or newly hidden product sends the customer back to catalogue search.
Out-of-stock but still-public products remain identifiable and are displayed as
currently unavailable.

## Invalid selections

Invalid selections increment the session clarification count and repeat the
approved options. After the configured maximum is exceeded, the workflow uses
the existing handover domain operation:

```text
CATALOGUE / PRODUCT_CLARIFICATION
    ↓ repeated invalid choices
HANDOVER / WAITING_FOR_HUMAN
HUMAN / PAUSED
```

The catalogue resolution and pending question are preserved for the person who
takes over.

Explicit "none of these" or human-assistance replies request handover
immediately without selecting a product.

## Safety guarantees

- NCPC and TradeFlow remain the only sources of product facts.
- Internal product IDs are not printed in customer replies.
- Candidate options are bounded by ProductResolver.
- Candidate sets cannot be used across businesses, customers, sessions, or
  beyond their expiry.
- Only public TradeFlow products are displayed.
- Live TradeFlow facts are re-read before product detail output.
- Raw dependency exceptions are never sent to customers.
- Expected dependency failures retain retryable/non-retryable classification.
- Invalid selection cannot silently choose a product.
- Search never automatically selects a top candidate.
- Product clarification state survives safe interruptions and handover.

## Run checks

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy ntheemba tests
```

## Next phase

Phase 10 implements the order workflow:

```text
ntheemba/workflows/
└── order.py
```

It will create and update `OrderDraft`, reuse catalogue resolution, collect
quantity and fulfilment, revalidate live price and stock, review, confirm, and
submit an idempotent TradeFlow order request.
