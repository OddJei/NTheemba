# Affiliate Metrics Reference

## Metrics Tracked in Affiliate-Engine

### AffiliateMetrics Dataclass
Located in: `services/affiliate-engine/src/app/pool.py` (lines 20-35)

```python
@dataclass
class AffiliateMetrics:
    affiliate_id: str
    sales_volume: float              # Total GMV (Gross Merchandise Value) in ZMW
    unique_buyers: int               # Distinct buyer phone numbers with sales in epoch
    msme_referrals: int              # Unique businesses referred (first-ever sale rule)
    clicks: int                       # Unique customer clicks (first-ever click rule)
    attributions: int                # Distinct orders attributed (conversions)
    paid_attributions: int           # Distinct orders that became paid sales
    tier_name: Optional[str]         # Current affiliate tier (bronze/silver/gold)
    tier_multiplier: float           # Multiplier for commission (1.0 to 3.0)
```

## Metrics Calculation Details

### 1. Sales Volume (GMV)
- **Source**: `AffiliateEvent` table, event_type = "sale"
- **Field**: `amount_zmw`
- **Calculation**: Sum of all sale amounts per affiliate per epoch
- **Gate**: Optionally gated on delivery confirmation (controlled by `_gate_on_delivery()`)
- **Importance**: Core metric for affiliate tier qualification and pool distribution

### 2. Unique Buyers
- **Source**: `AffiliateEvent` table, event_type = "sale"
- **Grouping**: Distinct `buyer_phone` per epoch per affiliate
- **Calculation**: Count of distinct phone numbers with completed sales
- **Purpose**: Measures affiliate reach and customer diversity

### 3. MSME Referrals
- **Source**: `AffiliateEvent` table, event_type = "sale"
- **Uniqueness Rule**: "Once, ever" - counts business only on its first-ever sale
- **Grouping**: Distinct `business_id` per affiliate
- **Calculation**: Count of unique businesses referred
- **Purpose**: Incentivizes affiliate efforts to grow the MSME network

### 4. Clicks (Customer Acquisition)
- **Source**: `AffiliateEvent` table, event_type = "campaign_click"
- **Uniqueness Rule**: "Once, ever" - counts each phone number only on first click
- **Calculation**: Distinct customer IDs (buyer_phone) per affiliate per epoch
- **Purpose**: Measures affiliate marketing effectiveness

### 5. Attributions (Conversions)
- **Source**: `AffiliateEvent` table, event_type = "conversion"
- **Calculation**: Distinct order count per affiliate per epoch
- **Purpose**: Tracks conversion rate (orders attributed)

### 6. Paid Attributions
- **Source**: `AffiliateEvent` table, event_type = "sale"
- **Calculation**: Distinct paid order count per affiliate per epoch
- **Purpose**: Tracks actual completed transactions

## Tier Qualification Thresholds

### Tier Structure: Bronze → Silver → Gold

Defaults (customizable via environment variables):

#### Bronze Tier
```
AFFILIATE_TIER_BRONZE_GMV_MIN_ZMW:       15,000.00
AFFILIATE_TIER_BRONZE_BUYERS_MIN:        60
AFFILIATE_TIER_BRONZE_REFERRALS_MIN:     6
AFFILIATE_TIER_BRONZE_CUSTOMERS_MIN:     120
Commission Multiplier:                    1.0x
```

#### Silver Tier
```
AFFILIATE_TIER_SILVER_GMV_MIN_ZMW:       40,000.00
AFFILIATE_TIER_SILVER_BUYERS_MIN:        150
AFFILIATE_TIER_SILVER_REFERRALS_MIN:     15
AFFILIATE_TIER_SILVER_CUSTOMERS_MIN:     300
Commission Multiplier:                    2.0x
```

#### Gold Tier
```
AFFILIATE_TIER_GOLD_GMV_MIN_ZMW:         80,000.00
AFFILIATE_TIER_GOLD_BUYERS_MIN:          300
AFFILIATE_TIER_GOLD_REFERRALS_MIN:       30
AFFILIATE_TIER_GOLD_CUSTOMERS_MIN:       600
Commission Multiplier:                    3.0x
```

## Weighted Scoring System

### Default Weights
Located in: `services/affiliate-engine/src/app/pool.py` (lines 36-40)

```python
_DEFAULT_OP_WEIGHTS: Dict[str, float] = {
    "sales_volume": 0.5,           # 50% weight - dominates scoring
    "unique_buyers": 0.2,          # 20% weight - customer diversity
    "msme_referrals": 0.2,         # 20% weight - network growth
    "conversion_quality": 0.1,     # 10% weight - conversion efficiency
}
```

### Scoring Calculation
- Affiliates are ranked using weighted scores of their metrics
- Scores determine pool allocation (commission distribution)
- Higher weight on sales_volume ensures revenue-focused incentives
- Balanced weights on buyers and referrals incentivize growth

## Event Types Tracked

| Event Type | Source | Purpose |
|-----------|--------|---------|
| `campaign_click` | Affiliate link clicks | Measure marketing reach |
| `conversion` | Order attribution | Track conversion rate |
| `sale` | Payment completed | Calculate commission & GMV |

## Endpoints That Use Metrics

1. **GET /pool/{epoch_id}/metrics**
   - Returns computed metrics for an epoch
   - Includes raw metrics, OP scores, and debug details
   - Admin endpoint

2. **GET /metrics**
   - Prometheus metrics endpoint
   - Exposes HTTP request counts and latency
   - Public endpoint (no auth required)

3. **POST /admin/epoch/{epoch_id}/close**
   - Closes epoch and triggers pool allocation
   - Uses metrics to compute payouts
   - Admin endpoint

## Database Tables

Metrics are derived from:
- `affiliate_engine.affiliate_events` - Primary source of metric data
- `affiliate_engine.affiliates` - Affiliate tier assignments
- `affiliate_engine.affiliate_tier_assignments` - Tier history tracking

## Environment Variable Overrides

All thresholds and weights can be customized via environment variables:

```bash
# Tier thresholds
AFFILIATE_TIER_BRONZE_GMV_MIN_ZMW=15000
AFFILIATE_TIER_SILVER_GMV_MIN_ZMW=40000
AFFILIATE_TIER_GOLD_GMV_MIN_ZMW=80000

# Customer count minimums
AFFILIATE_TIER_BRONZE_CUSTOMERS_MIN=120
AFFILIATE_TIER_SILVER_CUSTOMERS_MIN=300
AFFILIATE_TIER_GOLD_CUSTOMERS_MIN=600

# Commission weights (must sum to 1.0)
# Set via CommissionSettings.weights in database
```

## Customization Points

To modify affiliate metrics:

1. **Add new metric to AffiliateMetrics dataclass** (pool.py line ~20)
   ```python
   new_metric: float
   ```

2. **Add calculation in compute_metrics_for_epoch()** (pool.py line ~316)
   ```python
   # Query and compute new metric
   new_metric_rows = await db.execute(...)
   new_metrics_by_aff = {str(aid): value for aid, value in new_metric_rows}
   ```

3. **Include in returned metrics** (pool.py line ~460)
   ```python
   AffiliateMetrics(
       ...
       new_metric=new_metrics_by_aff.get(affiliate_id, 0),
   )
   ```

4. **Update scoring if adding to weights** (pool.py line ~36)
   ```python
   _DEFAULT_OP_WEIGHTS["new_metric"] = 0.1  # Adjust weights to sum to 1.0
   ```

## Current Configuration (Production)

- **Gating**: Sales volume is gated on delivery confirmation
- **Uniqueness**: All metrics follow "once, ever" uniqueness rule per epoch
- **Scoring**: 5 metrics weighted with sales_volume at 50%
- **Tiers**: 3 tiers (bronze/silver/gold) with 1.0x, 2.0x, 3.0x multipliers
- **Update Frequency**: Metrics computed on epoch close or admin request

