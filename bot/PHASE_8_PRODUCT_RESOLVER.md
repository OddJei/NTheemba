# Phase 8 — NCPC Product Resolver

Phase 8 implements product identity resolution before catalogue and order
workflows are added.

## Added files

```text
ntheemba/services/
└── product_resolver.py

tests/unit/services/
└── test_product_resolver.py
```

## Ownership boundary

```text
Customer language
    ↓
NCPC
Canonical identity, brand, family, variant, size, barcode, category
    ↓
TradeFlow
Whether this business sells it, public visibility, price, stock state
    ↓
Ntheemba ProductResolver
Rank and return a customer-confirmed candidate set
```

The model or interpreter cannot provide price, stock, internal IDs, or final
availability. Those fields enter only after TradeFlow filtering.

## Resolution outcomes

The resolver returns these domain statuses:

- `NO_MATCH`
- `ONE_MATCH`
- `NEEDS_CLARIFICATION`
- `RESOLVED`

`RESOLVED` is only produced from a customer selection against a saved pending
candidate set. Product search never silently selects a top result, even when
NCPC confidence is high.

### Search resolution

Search sends all returned NCPC variant IDs to the selected business's TradeFlow
catalogue in one batch. TradeFlow filters that batch to public, shop-relevant
business products and supplies display facts such as name, price, currency, and
availability. The resolver then returns either one confirmable candidate or a
bounded set of choices, normally three to five when enough public matches exist.

### Confirmation instead of guessing

One public business match produces `ONE_MATCH`; multiple public business matches
produce `NEEDS_CLARIFICATION`.

Example:

```text
Customer: I need the small Boom.
Ntheemba: I found more than one possible product:
1. Boom Washing Powder 250g (ZMW 15.00, currently unavailable)
2. Boom Washing Powder 500g (ZMW 24.00, available)
3. Boom Washing Powder 1kg (ZMW 42.00, available)
```

### Controlled clarification

Several plausible business products produce numbered, customer-safe options
with TradeFlow display details. Internal NCPC and TradeFlow IDs are never
included in clarification labels.

## Relative sizes

Comparable sizes are normalized before ranking:

```text
250g → 250 grams
500g → 500 grams
1kg  → 1000 grams
```

The resolver supports:

- smallest
- small
- medium
- large
- largest

Relative-size language reorders the candidate set toward the requested size. It
does not automatically select the item.

## Customer selection

`resolve_selection()` accepts:

- a one-based option number;
- a numbered string such as `2` or `2.`;
- an exact candidate name;
- a unique size such as `500g`;
- an affirmative reply only when exactly one candidate is pending.

Ambiguous or invalid selection raises `ProductSelectionError`.

## Safety guarantees

- NCPC search is bounded.
- Candidate output is bounded.
- Duplicate NCPC products are removed.
- Products absent from the business catalogue are removed.
- Non-public TradeFlow products are removed defensively.
- Out-of-stock public products may still resolve, but their availability is
  preserved as false.
- Final customer selection requires business product identity, NCPC product ID,
  NCPC variant ID, price, currency, and availability.
- Ranking does not use price to infer identity.
- No HTTP, Redis, FastAPI, or workflow code is imported.

## Run checks

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy ntheemba tests
```

## Next phase

Phase 9 implements the catalogue workflow:

```text
ntheemba/workflows/
└── catalogue.py
```

It will connect interpretation, ProductResolver, session product-resolution
state, ResponseBuilder, product details, selection, and transition control.
