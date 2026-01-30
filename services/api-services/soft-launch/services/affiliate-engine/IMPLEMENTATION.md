# Affiliate Engine — Implementation Guide (Soft Launch)

This document explains (in simple terms) how the Affiliate Engine works and how the **affiliate pool** is computed.

If you are a student: think of this system like a **scoreboard + wallet**.
- The scoreboard tracks who helped the platform (clicks, buyers, referrals, sales).
- The wallet decides who gets paid from a shared “pool”.

---

## 1) What this service does

The Affiliate Engine is responsible for:
- Creating affiliates
- Creating affiliate links
- Tracking link clicks (who brought customers)
- Attributing orders to affiliates
- Receiving payment success events and recording affiliate earnings
- Computing the **affiliate pool** standings and final payouts for each epoch (season)

---

## 2) Important words (quick glossary)

- **Affiliate**: a person who promotes MSME products using a link.
- **Affiliate link**: a short code like `codeA` that points to a product/business.
- **Click**: someone clicked the affiliate link (we store the phone number if we have it).
- **Attribution**: we connected an order to an affiliate link.
- **Sale**: payment succeeded for an order.
- **Epoch**: a “season” (usually ~6 months). The pool is calculated per epoch.
- **Pool**: money set aside for affiliates (defaults to **10%** of gross revenue for that epoch).

---

## 3) Where data is stored (tables)

Most pool scoring uses the **append-only event log** table:
- `affiliate_events`

Other tables you’ll see:
- `affiliate_links` (the codes)
- `affiliate_clicks` (click records)
- `affiliate_attributions` (order attribution)
- `affiliate_earnings` (affiliate money per sale)
- `commission_settings` (pool_pct, epoch_days, weights)
- `pool_epochs` (open/closed epochs; gross_revenue_zmw)
- `pool_allocations` (final payout per affiliate after closing an epoch)

---

## 4) The pool scoring formula (what the code does)

### 4.1 Metrics and weights (defaults)

The pool score uses four metrics:

1. **Sales volume** (weight 50%)
2. **Unique buyers** (weight 20%)
3. **MSME referrals** (weight 20%)
4. **Conversion quality = unique customers** (weight 10%)

In code, “conversion_quality” is treated as:
- **Unique customers = distinct phone numbers brought to the bot**

Important note:
- Uniqueness is **once, ever** across epochs (pool resets). A phone only counts the first time it appears.

### 4.2 Normalization (to keep it fair)

For each metric, we compare everyone to the best performer.

If the best person has 100 buyers and you have 50 buyers, your normalized buyers score is:

$$
\text{buyers_normalized} = \frac{50}{100} = 0.5
$$

### 4.3 Weighted score

The raw score is:

$$
\text{Score} = 0.5\cdot S + 0.2\cdot B + 0.2\cdot R + 0.1\cdot C
$$

Where:
- $S$ = normalized sales volume
- $B$ = normalized unique buyers
- $R$ = normalized MSME referrals
- $C$ = normalized unique customers

### 4.4 Tier multipliers (bronze/silver/gold)

Tiers multiply the score:
- bronze: 1.3×
- silver: 1.5×
- gold: 1.8×

In code today:
- A tier multiplier only applies if the affiliate **qualifies** for that tier.
- Qualification rule: meet thresholds in **at least 2** of the 4 metrics for that tier.
- Auto-upgrade: if you meet **all 4** thresholds for your tier, you auto-upgrade one tier for the multiplier.

### 4.5 Final payout

Let the pool amount be `pool_amount_zmw`.
Let all adjusted scores sum to $T$.
Your payout is:

$$
\text{Payout} = \frac{\text{your_score}}{T} \times \text{pool_amount}
$$

---

## 5) How events feed the pool

The pool metrics are derived from `affiliate_events`.
Event types used:
- `campaign_click` → counts toward unique customers (distinct phones)
- `conversion` → order attribution created
- `sale` → payment success (money)

So the pool is “events-only”: if an event isn’t written, it can’t affect the pool.

---

## 6) Admin workflow (how you run a pool epoch)

Typical flow:
1. Open an epoch (or reuse the current open epoch)
2. Set gross revenue (ZMW) for that epoch
3. View standings
4. Close the epoch to write final allocations

---

## 7) Checklist (do this step-by-step)

### Setup & run
- [ ] Create a venv and install requirements
- [ ] Set `DATABASE_URL` (or use default sqlite)
- [ ] Start the service: `uvicorn src.app.main:app --reload --port 8510`
- [ ] Open Swagger docs at `http://127.0.0.1:8510/docs`

### Create sample data
- [ ] Create an affiliate: `POST /affiliates`
- [ ] Create an affiliate link: `POST /affiliates/{affiliate_id}/links`
- [ ] Track a click: `POST /track/click`
- [ ] Attribute an order: `POST /attribute/order`
- [ ] Send payment success: `POST /events/payment-success`

### Pool controls (admin)
- [ ] Check current settings: `GET /admin/commission-settings` (requires `X-Admin-Key`)
- [ ] Update pool percent / weights if needed: `PUT /admin/commission-settings`
- [ ] List epochs: `GET /admin/epochs`
- [ ] Set epoch gross revenue: `PUT /admin/epochs/{epoch_id}/gross-revenue`
- [ ] View projected standings: `GET /pool/standings`
- [ ] Close epoch and store final payouts: `POST /admin/epochs/{epoch_id}/close`
- [ ] View saved allocations: `GET /admin/epochs/{epoch_id}/allocations`

### Testing
- [ ] Run tests: `pytest -q`
- [ ] Confirm `test_pool_allocations_sum_to_pool_and_rankings` passes
- [ ] Confirm `test_tier_multiplier_increases_share` passes

---

## 8) Key files to read first

- Pool logic (math + allocations):
  - `src/app/pool.py`
- API endpoints:
  - `src/app/main.py`
- Database models:
  - `src/app/models.py`
- Pool tests:
  - `tests/test_pool.py`
