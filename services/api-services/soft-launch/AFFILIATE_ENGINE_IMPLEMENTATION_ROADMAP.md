# Affiliate Engine Implementation Roadmap

**Last Updated:** February 3, 2026

---

## Overview

Complete overhaul of affiliate scoring, payout, and ledger system to support real-time earnings visibility, automated payout processing, and transparent payment tracking.

---

## Phase 1: Real-Time Score Calculation & Projected Payouts

### Objective

Enable affiliates to see projected earnings in real-time based on current metrics without waiting for epoch close.

### Implementation

#### 1.1 Add Projected Payout Endpoint

**File:** `services/affiliate-engine/src/app/main.py`

```python
@app.get("/affiliates/{affiliate_id}/projected-payout", response_model=ProjectedPayoutOut)
async def get_projected_payout(
    affiliate_id: str,
    db: AsyncSession = Depends(db_session),
    x_token: str = Header(alias="X-Affiliate-Token")
):
    """
    Calculate real-time projected payout for current epoch.
    
    Returns:
    - Current metrics (sales_volume, unique_buyers, msme_referrals, clicks, attributions, session_cycles)
    - Weighted score
    - Tier qualification status
    - Effective tier and multiplier
    - Projected payout amount (if epoch ended today)
    
    Uses CURRENT open epoch and REAL GROSS REVENUE from payment-revenue service.
    """
    # 1. Verify affiliate
    # 2. Get current open epoch
    # 3. Fetch affiliate metrics from current epoch
    # 4. Get tier thresholds from DB
    # 5. Calculate scores in real-time
    # 6. Get gross revenue from payment-revenue service
    # 7. Calculate projected payout
    # 8. Return ProjectedPayoutOut
```

#### 1.2 New Schema: ProjectedPayoutOut

**File:** `services/affiliate-engine/src/app/schemas.py`

```python
class ProjectedPayoutOut(BaseModel):
    affiliate_id: str
    epoch_id: str
    epoch_ends_at: datetime
    
    # Metrics
    sales_volume: float
    unique_buyers: int
    msme_referrals: int
    clicks: int
    attributions: int
    paid_attributions: int
    session_cycles: int
    
    # Scoring
    weighted_score: float
    
    # Tier qualification
    qualified_tiers: list[str]  # e.g., ["bronze", "silver"]
    effective_tier: str  # Highest qualified tier
    tier_multiplier: float
    
    # Payout calculation
    gross_revenue_zmw: float
    pool_pct: float
    pool_amount_zmw: float
    affiliate_share_pct: float
    projected_payout_zmw: float
```

---

## Phase 2: Gross Revenue Integration with Payment-Revenue Service

### Objective

Calculate **gross revenue** in payment-revenue and expose it to affiliate-engine, plus track the **total money currently held on the platform** for analytics/audit.

**Gross Revenue definition:**
- `gross_revenue_zmw = subscription_revenue_zmw + platform_fee_revenue_zmw`
- `platform_fee_revenue_zmw` counts **completed orders only** (paid + delivered + MSME payout completed).

**Total money on platform (current balance):**
- `platform_balance_zmw = total_inflows_zmw - total_outflows_zmw`
- Inflows: subscriptions + platform fees
- Outflows: MSME payouts + affiliate payouts + refunds

### Implementation

#### 2.1 Add Revenue Ledger & Gross Revenue Calculation in Payment-Revenue

**File:** `services/payment-revenue/src/app/main.py`

```python
@app.get("/admin/gross-revenue", response_model=GrossRevenueOut)
async def get_gross_revenue(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: AsyncSession = Depends(db_session),
    x_admin_key: str = Header(alias="X-Admin-Key")
):
    """
    Calculate gross revenue for a date range.
    
    Gross Revenue = subscription revenue + platform fee revenue
    Platform fee revenue = orders that are paid + delivered + MSME payout completed
    
    Returns:
    - gross_revenue_zmw
    - subscription_revenue_zmw
    - platform_fee_revenue_zmw
    - transaction_count
    - start_date, end_date
    - calculated_at
    """
    # Query subscription payments (success)
    # Query order platform fees where order is paid+delivered and MSME payout is completed
    # Sum into gross_revenue_zmw
```

#### 2.2 Add Epoch-Scoped Revenue Query

**File:** `services/payment-revenue/src/app/main.py`

```python
@app.get("/epoch/{epoch_id}/gross-revenue", response_model=GrossRevenueOut)
async def get_epoch_gross_revenue(
    epoch_id: str,
    db: AsyncSession = Depends(db_session),
    x_admin_key: str = Header(alias="X-Admin-Key")
):
    """
    Get gross revenue for a specific epoch period.
    
    Uses epoch.starts_at and epoch.ends_at to filter:
    - subscription payments
    - completed-order platform fees (paid + delivered + MSME payout completed)
    """
    # Get epoch from affiliate-engine
    # Calculate subscription_revenue_zmw + platform_fee_revenue_zmw
    # Return GrossRevenueOut

#### 2.3 Add Platform Balance (Total Money on Platform)

**File:** `services/payment-revenue/src/app/main.py`

```python
@app.get("/admin/platform-balance", response_model=PlatformBalanceOut)
async def get_platform_balance(
    db: AsyncSession = Depends(db_session),
    x_admin_key: str = Header(alias="X-Admin-Key")
):
    """
    Current total money held on the platform.

    platform_balance_zmw = (subscriptions + platform_fees)
                           - (msme_payouts + affiliate_payouts + refunds)

    Returns:
    - platform_balance_zmw
    - total_inflows_zmw
    - total_outflows_zmw
    - calculated_at
    """
    # Aggregate inflows/outflows from ledger tables
```
```

#### 2.4 Update Affiliate-Engine Config

**File:** `services/affiliate-engine/src/app/config.py`

```python
def get_payment_revenue_base_url() -> str:
    return os.getenv("PAYMENT_REVENUE_BASE_URL", "http://127.0.0.1:8560")
```

**File:** `docker-compose.yml`

```yaml
affiliate-engine:
  environment:
    PAYMENT_REVENUE_BASE_URL: http://payment-revenue:8560
```

#### 2.5 Service Call in Affiliate-Engine

**File:** `services/affiliate-engine/src/app/pool.py`

```python
async def fetch_gross_revenue(db: AsyncSession, epoch: PoolEpoch) -> float:
    """
    Fetch actual gross revenue from payment-revenue service.
    
    Falls back to epoch.gross_revenue_zmw if service unavailable.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{get_payment_revenue_base_url()}/epoch/{epoch.id}/gross-revenue",
                headers={"X-Admin-Key": get_admin_key()},
                timeout=5.0
            )
            if response.status_code == 200:
                data = response.json()
                return float(data["gross_revenue_zmw"])
    except Exception as e:
        log.warning(f"Failed to fetch gross revenue: {e}")
    
    # Fallback to admin-set value
    return float(epoch.gross_revenue_zmw) if epoch.gross_revenue_zmw else 0.0
```

---

## Phase 2.5: MSME Payout Integration on Order Delivery

### Objective

Automatically pay MSME when order is delivered. Validate subscription, apply platform fees, and record full gross revenue.

### Implementation

#### 2.5.1 Listen to Order Delivered Events

**File:** `services/payment-revenue/src/app/main.py`

Payment-Revenue subscribes to `order_delivered` events from order-delivery service.

```python
async def handle_order_delivered_event(event: OrderDeliveredEvent):
    """
    Triggered when order is confirmed delivered.
    
    FLOW:
    1. Validate MSME subscription status
    2. Calculate MSME payout (minus platform fee)
    3. Record full order amount as gross revenue
    4. Initiate PawaPay payout to MSME
    5. Track payout status
    """
    order_id = event.order_id
    business_id = event.business_id
    order_amount = event.order_amount  # Full amount (before any deductions)
    
    # 1. Record full order amount as gross revenue
    await record_gross_revenue(db, order_id, business_id, order_amount)
    
    # 2. Validate MSME subscription
    msme_subscription = await validate_msme_subscription(business_id)
    if not msme_subscription.active:
        log.warning(f"MSME {business_id} inactive - skipping payout for order {order_id}")
        return
    
    # 3. Calculate payout amount
    platform_fee_pct = msme_subscription.platform_fee_pct
    platform_fee_amount = order_amount * platform_fee_pct
    msme_payout_amount = order_amount - platform_fee_amount
    
    # 4. Initiate MSME payout via PawaPay
    payout_result = await initiate_msme_payout(
        order_id=order_id,
        business_id=business_id,
        msme_phone=msme_subscription.phone,
        amount_zmw=msme_payout_amount,
        platform_fee_zmw=platform_fee_amount,
        callback_url=f"{get_base_url()}/callbacks/msme-payout-status"
    )
    
    # 5. Track payout
    await store_msme_payout_record(
        db,
        order_id=order_id,
        business_id=business_id,
        payout_id=payout_result.payout_id,
        amount_zmw=msme_payout_amount,
        platform_fee_zmw=platform_fee_amount,
        status="processing"
    )
```

#### 2.5.2 MSME Subscription Validation

**File:** `services/payment-revenue/src/app/services/msme.py`

```python
async def validate_msme_subscription(business_id: str) -> MSMESubscription:
    """
    Call MSME-Engine to validate subscription and get platform fee.
    
    Endpoint: GET /msme/{business_id}/subscription
    
    Returns:
    - active: bool
    - platform_fee_pct: float (e.g., 0.05 for 5%)
    - phone: str
    - tier: str
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{get_msme_base_url()}/msme/{business_id}/subscription",
            headers={"X-Admin-Key": get_admin_key()},
            timeout=5.0
        )
        
        if response.status_code == 200:
            data = response.json()
            return MSMESubscription(
                active=data.get("active", False),
                platform_fee_pct=float(data.get("platform_fee_pct", 0.05)),
                phone=data.get("phone"),
                tier=data.get("tier")
            )
        else:
            log.error(f"Failed to validate MSME {business_id}: {response.status_code}")
            # Default to inactive if validation fails
            return MSMESubscription(active=False, platform_fee_pct=0.05, phone=None, tier=None)
```

#### 2.5.3 Gross Revenue Recording

**File:** `services/payment-revenue/src/app/models.py`

```python
class GrossRevenueRecord(Base):
    __tablename__ = "gross_revenue_records"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id"))
    business_id: Mapped[str] = mapped_column(String(36))
    
    # Full order amount (before any deductions)
    amount_zmw: Mapped[float] = mapped_column(Float)
    
    # Breakdown
    msme_payout_zmw: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    platform_fee_zmw: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    affiliate_pool_zmw: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Status
    status: Mapped[str] = mapped_column(String(50), default="recorded")  # recorded, allocated
    
    epoch_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    
    recorded_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
```

#### 2.5.4 Epoch-Scoped Gross Revenue Query

**File:** `services/payment-revenue/src/app/main.py`

```python
@app.get("/admin/epoch/{epoch_id}/gross-revenue", response_model=GrossRevenueOut)
async def get_epoch_gross_revenue(
    epoch_id: str,
    db: AsyncSession = Depends(db_session),
    x_admin_key: str = Header(alias="X-Admin-Key")
):
    """
    Calculate gross revenue for a specific epoch.
    
    Gross Revenue = SUM of all order_amount for orders delivered during epoch period
    
    Uses epoch.starts_at and epoch.ends_at to filter.
    
    Returns:
    - gross_revenue_zmw: Total of all orders (full amounts)
    - transaction_count: Number of orders
    - msme_payout_total: Sum of MSME payouts
    - platform_fee_total: Sum of platform fees
    - epoch_starts_at, epoch_ends_at: Period
    - calculated_at: Timestamp
    """
    # Get epoch dates from affiliate-engine
    # Query GrossRevenueRecord where recorded_at BETWEEN epoch.starts_at AND epoch.ends_at
    
    query = select(
        func.sum(GrossRevenueRecord.amount_zmw).label("gross_revenue_zmw"),
        func.count(GrossRevenueRecord.id).label("transaction_count"),
        func.sum(GrossRevenueRecord.msme_payout_zmw).label("msme_payout_total"),
        func.sum(GrossRevenueRecord.platform_fee_zmw).label("platform_fee_total"),
    ).where(
        GrossRevenueRecord.epoch_id == epoch_id
    )
    
    result = (await db.execute(query)).first()
    
    return GrossRevenueOut(
        epoch_id=epoch_id,
        gross_revenue_zmw=float(result[0] or 0),
        transaction_count=int(result[1] or 0),
        msme_payout_total=float(result[2] or 0),
        platform_fee_total=float(result[3] or 0),
        calculated_at=utcnow()
    )
```

#### 2.5.5 MSME Payout Record Model

**File:** `services/payment-revenue/src/app/models.py`

```python
class MSMEPayout(Base):
    __tablename__ = "msme_payouts"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    payout_id: Mapped[str] = mapped_column(String(36), unique=True)  # PawaPay payout ID
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id"))
    business_id: Mapped[str] = mapped_column(String(36))
    
    # Payout details
    amount_zmw: Mapped[float] = mapped_column(Float)  # Amount paid to MSME
    platform_fee_zmw: Mapped[float] = mapped_column(Float)  # Platform fee (retained)
    msme_phone: Mapped[str] = mapped_column(String(20))
    
    # Status tracking
    status: Mapped[str] = mapped_column(String(50), default="processing")  # processing, completed, failed
    error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    initiated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
```

#### 2.5.6 PawaPay Integration

**File:** `services/payment-revenue/src/app/services/pawapay.py`

```python
async def initiate_msme_payout(
    order_id: str,
    business_id: str,
    msme_phone: str,
    amount_zmw: float,
    platform_fee_zmw: float,
    callback_url: str,
) -> PayoutResult:
    """
    Initiate payout to MSME via PawaPay.
    
    Returns payout_id for tracking.
    """
    payload = {
        "accountNumber": msme_phone,
        "amount": int(amount_zmw * 100),  # Convert to cents
        "currency": "ZMW",
        "externalReference": order_id,
        "metadata": {
            "business_id": business_id,
            "order_id": order_id,
            "platform_fee": platform_fee_zmw,
            "callback_url": callback_url,
        }
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{get_pawapay_base_url()}/transfers",
            json=payload,
            headers={"Authorization": f"Bearer {get_pawapay_token()}"},
            timeout=10.0
        )
        
        if response.status_code in (200, 201):
            data = response.json()
            return PayoutResult(
                payout_id=data["transferId"],
                status="processing",
                amount_zmw=amount_zmw
            )
        else:
            log.error(f"PawaPay payout failed: {response.status_code} - {response.text}")
            raise PayoutException(f"PawaPay error: {response.status_code}")
```

#### 2.5.7 MSME Payout Callback Handler

**File:** `services/payment-revenue/src/app/main.py`

```python
@app.post("/callbacks/msme-payout-status")
async def handle_msme_payout_callback(
    payload: MSMEPayoutStatusCallback,
    db: AsyncSession = Depends(db_session),
):
    """
    Receive MSME payout status from PawaPay.
    
    Updates payout status and notifies affiliate-engine if needed.
    """
    payout = (
        await db.execute(
            select(MSMEPayout).where(MSMEPayout.payout_id == payload.payout_id)
        )
    ).scalar_one_or_none()
    
    if not payout:
        log.warning(f"Payout {payload.payout_id} not found")
        return {"status": "ok"}  # Still return 200 to PawaPay
    
    # Update status
    payout.status = payload.status  # completed, failed
    payout.completed_at = utcnow()
    
    if payload.status == "failed":
        payout.error_message = payload.error_message
        log.error(f"MSME payout {payload.payout_id} failed: {payload.error_message}")
    
    await db.commit()
    
    # Emit audit event
    await emit_audit_event(
        db,
        event_type="msme_payout_completed",
        business_id=payout.business_id,
        order_id=payout.order_id,
        meta={
            "payout_id": payload.payout_id,
            "status": payload.status,
            "amount_zmw": payout.amount_zmw,
            "error": payout.error_message,
        },
    )
    
    return {"status": "ok"}
```

#### 2.5.8 Schemas

**File:** `services/payment-revenue/src/app/schemas.py`

```python
class GrossRevenueOut(BaseModel):
    epoch_id: str
    gross_revenue_zmw: float
    transaction_count: int
    msme_payout_total: Optional[float]
    platform_fee_total: Optional[float]
    calculated_at: datetime

class MSMEPayoutStatusCallback(BaseModel):
    payout_id: str
    order_id: str
    status: Literal["completed", "failed"]
    error_message: Optional[str] = None
    completed_at: datetime

class MSMESubscription(BaseModel):
    active: bool
    platform_fee_pct: float
    phone: Optional[str]
    tier: Optional[str]
```

---

## Phase 3: Real-Time Ledger for Affiliates

### Objective

Track all affiliate transactions (clicks, attributions, payouts) in a real-time ledger for transparency and audit.

### Implementation

#### 3.1 Add AffiliateTransaction Model

**File:** `services/affiliate-engine/src/app/models.py`

```python
class AffiliateTransaction(Base):
    __tablename__ = "affiliate_transactions"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    affiliate_id: Mapped[str] = mapped_column(String(36), ForeignKey("affiliates.id"))
    epoch_id: Mapped[str] = mapped_column(String(36), ForeignKey("pool_epochs.id"))
    
    transaction_type: Mapped[str] = mapped_column(
        String(50)
    )  # "click", "attribution", "payout", "adjustment"
    
    # Amount in ZMW (only for payout/adjustment)
    amount_zmw: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Reference IDs
    click_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    attribution_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    order_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    pool_allocation_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("pool_allocations.id"), nullable=True
    )
    
    # Status and metadata
    status: Mapped[str] = mapped_column(String(50), default="recorded")  # recorded, pending, completed
    description: Mapped[str] = mapped_column(String(500), nullable=True)
    meta: Mapped[dict] = mapped_column(SqliteJson, default=dict)
    
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
```

#### 3.2 Log Transactions on Each Event

**File:** `services/affiliate-engine/src/app/main.py`

```python
async def log_affiliate_transaction(
    db: AsyncSession,
    affiliate_id: str,
    epoch_id: str,
    transaction_type: str,
    reference_id: Optional[str] = None,
    amount_zmw: Optional[float] = None,
    description: Optional[str] = None,
    meta: Optional[dict] = None,
):
    """Log transaction for audit and ledger."""
    transaction = AffiliateTransaction(
        affiliate_id=affiliate_id,
        epoch_id=epoch_id,
        transaction_type=transaction_type,
        click_id=reference_id if transaction_type == "click" else None,
        attribution_id=reference_id if transaction_type == "attribution" else None,
        amount_zmw=amount_zmw,
        description=description,
        meta=meta or {},
    )
    db.add(transaction)
    await db.commit()
```

**Usage in endpoints:**

- When click recorded: `log_affiliate_transaction(..., "click", ...)`
- When attribution recorded: `log_affiliate_transaction(..., "attribution", ...)`
- When payout allocated: `log_affiliate_transaction(..., "payout", ..., amount_zmw=...)`

#### 3.3 Add Ledger Query Endpoint

**File:** `services/affiliate-engine/src/app/main.py`

```python
@app.get("/affiliates/{affiliate_id}/ledger", response_model=list[TransactionOut])
async def get_affiliate_ledger(
    affiliate_id: str,
    epoch_id: Optional[str] = None,
    transaction_type: Optional[str] = None,
    limit: int = 100,
    db: AsyncSession = Depends(db_session),
    x_token: str = Header(alias="X-Affiliate-Token")
):
    """
    Get transaction ledger for affiliate.
    
    Filters:
    - By epoch (optional)
    - By transaction_type (optional: click, attribution, payout, adjustment)
    
    Returns paginated list ordered by newest first.
    """
    query = select(AffiliateTransaction).where(
        AffiliateTransaction.affiliate_id == affiliate_id
    )
    
    if epoch_id:
        query = query.where(AffiliateTransaction.epoch_id == epoch_id)
    if transaction_type:
        query = query.where(AffiliateTransaction.transaction_type == transaction_type)
    
    query = query.order_by(AffiliateTransaction.created_at.desc()).limit(limit)
    
    rows = (await db.execute(query)).scalars().all()
    
    return [TransactionOut.from_orm(r) for r in rows]
```

#### 3.4 New Schema: TransactionOut

**File:** `services/affiliate-engine/src/app/schemas.py`

```python
class TransactionOut(BaseModel):
    id: str
    affiliate_id: str
    epoch_id: str
    transaction_type: str  # click, attribution, payout, adjustment
    amount_zmw: Optional[float]
    description: Optional[str]
    status: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
```

---

## Phase 4: Payment Flow Integration

### Objective

Complete payment pipeline: epoch close → payment-revenue payout request → callback handling → status updates.

### Implementation

#### 4.1 Add Payout Status Tracking

**File:** `services/affiliate-engine/src/app/models.py`

```python
class PoolAllocation(Base):
    # ... existing fields ...
    
    # NEW: Payout status tracking
    payout_status: Mapped[str] = mapped_column(
        String(50), default="pending"
    )  # pending, processing, completed, failed
    payout_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    payout_initiated_at: Mapped[Optional[dt.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    payout_completed_at: Mapped[Optional[dt.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    payout_error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
```

#### 4.2 Update Epoch Close to Request Payout

**File:** `services/affiliate-engine/src/app/pool.py`

```python
async def close_epoch_and_allocate(
    db: AsyncSession, epoch: PoolEpoch, settings: CommissionSettings
) -> list[PoolAllocation]:
    """
    Close epoch and allocate payouts.
    
    FLOW:
    1. Calculate scores for all affiliates
    2. Create PoolAllocation records
    3. Get gross revenue from payment-revenue
    4. Request payout from payment-revenue service
    5. Store payout_id in allocations
    6. Set payout_status = "processing"
    """
    
    # ... existing allocation logic ...
    
    # Get actual gross revenue
    gross_revenue = await fetch_gross_revenue(db, epoch)
    
    # Calculate pool
    pool_amount = gross_revenue * float(settings.pool_pct)
    
    # Create allocations with payout amounts
    allocations = []
    total_score = sum(a.weighted_score for a in allocations)
    
    for allocation in allocations:
        allocation.payout_zmw = (allocation.weighted_score / total_score) * pool_amount
        allocation.payout_status = "pending"
    
    await db.commit()
    
    # Request payout from payment-revenue
    await request_payout_from_payment_revenue(db, epoch.id, allocations)
    
    return allocations
```

#### 4.3 Add Payout Request to Payment-Revenue

**File:** `services/affiliate-engine/src/app/main.py`

```python
async def request_payout_from_payment_revenue(
    db: AsyncSession,
    epoch_id: str,
    allocations: list[PoolAllocation]
):
    """
    Send payout batch request to payment-revenue service.
    
    Expects response with payout_id for tracking.
    """
    payout_batch = {
        "epoch_id": epoch_id,
        "payouts": [
            {
                "affiliate_id": a.affiliate_id,
                "amount_zmw": float(a.payout_zmw),
                "currency": "ZMW",
                "callback_url": f"{get_base_url()}/callbacks/payout-status",
            }
            for a in allocations
        ],
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{get_payment_revenue_base_url()}/payout/batch",
                json=payout_batch,
                headers={"X-Admin-Key": get_admin_key()},
                timeout=10.0,
            )
            
            if response.status_code == 202:
                data = response.json()
                payout_id = data["payout_id"]
                
                # Update all allocations with payout_id
                for allocation in allocations:
                    allocation.payout_id = payout_id
                    allocation.payout_status = "processing"
                    allocation.payout_initiated_at = utcnow()
                
                await db.commit()
                
                log.info(f"Payout batch {payout_id} initiated for epoch {epoch_id}")
            else:
                log.error(f"Payout request failed: {response.status_code}")
    except Exception as e:
        log.error(f"Failed to request payout: {e}")
```

#### 4.4 Add Payout Callback Handler

**File:** `services/affiliate-engine/src/app/main.py`

```python
@app.post("/callbacks/payout-status")
async def handle_payout_status_callback(
    payload: PayoutStatusCallback,
    db: AsyncSession = Depends(db_session),
):
    """
    Receive payout status updates from payment-revenue service.
    
    Updates allocation status and creates transaction records.
    """
    allocation = (
        await db.execute(
            select(PoolAllocation).where(PoolAllocation.payout_id == payload.payout_id)
        )
    ).scalar_one_or_none()
    
    if not allocation:
        raise HTTPException(status_code=404, detail="allocation_not_found")
    
    # Update payout status
    allocation.payout_status = payload.status  # completed, failed
    allocation.payout_completed_at = utcnow()
    
    if payload.status == "failed":
        allocation.payout_error = payload.error_message
        log.error(f"Payout failed for {allocation.affiliate_id}: {payload.error_message}")
    
    await db.commit()
    
    # Log transaction
    await log_affiliate_transaction(
        db,
        allocation.affiliate_id,
        allocation.epoch_id,
        "payout",
        amount_zmw=float(allocation.payout_zmw),
        description=f"Payout {payload.status}",
        meta={"payout_id": payload.payout_id, "status": payload.status},
    )
    
    # Emit audit event
    await emit_audit_event(
        db,
        event_type="affiliate_payout_completed",
        affiliate_id=allocation.affiliate_id,
        meta={
            "epoch_id": allocation.epoch_id,
            "payout_id": payload.payout_id,
            "amount_zmw": float(allocation.payout_zmw),
            "status": payload.status,
        },
    )
    
    return {"status": "ok"}
```

#### 4.5 New Schema: PayoutStatusCallback

**File:** `services/affiliate-engine/src/app/schemas.py`

```python
class PayoutStatusCallback(BaseModel):
    payout_id: str
    epoch_id: str
    affiliate_id: str
    status: Literal["completed", "failed"]
    amount_zmw: float
    error_message: Optional[str] = None
    completed_at: datetime
```

---

## Phase 5: Dashboard Enhancements

### Objective

Provide comprehensive affiliate dashboards with real-time earnings and ledger visibility.

### Implementation

#### 5.1 Enhanced Dashboard Endpoint

**File:** `services/affiliate-engine/src/app/main.py`

```python
@app.get("/affiliates/{affiliate_id}/dashboard", response_model=AffiliateDashboardV2)
async def get_affiliate_dashboard_v2(
    affiliate_id: str,
    db: AsyncSession = Depends(db_session),
    x_token: str = Header(alias="X-Affiliate-Token")
):
    """
    Comprehensive affiliate dashboard.
    
    Includes:
    - Current epoch projected payout
    - Previous epoch actual payout
    - Total lifetime earnings
    - Recent transactions (clicks, attributions, payouts)
    - Tier qualification status
    - Performance metrics
    """
    # 1. Get affiliate
    # 2. Get open epoch + projected payout
    # 3. Get last closed epoch + actual payout
    # 4. Get lifetime stats
    # 5. Get recent transactions
    # 6. Return combined dashboard
```

#### 5.2 Enhanced Dashboard Schema

**File:** `services/affiliate-engine/src/app/schemas.py`

```python
class AffiliateDashboardV2(BaseModel):
    affiliate_id: str
    name: str
    
    # Current Epoch
    current_epoch: Optional[EpochOut]
    projected_payout: Optional[ProjectedPayoutOut]
    
    # Previous Epoch
    previous_epoch: Optional[EpochOut]
    actual_payout: Optional[float]
    payout_status: Optional[str]  # completed, failed, pending
    
    # Lifetime Stats
    total_payouts: float
    total_clicks: int
    total_attributions: int
    
    # Recent Activity
    recent_transactions: list[TransactionOut]
    
    # Status
    account_status: str
    created_at: datetime
```

---

## Phase 6: Admin Dashboards & Reporting

### Objective

Provide operators with visibility into pool allocation, payout status, and payment reconciliation.

### Implementation

#### 6.1 Epoch Summary Endpoint

**File:** `services/affiliate-engine/src/app/main.py`

```python
@app.get("/admin/epochs/{epoch_id}/summary", response_model=EpochSummary)
async def get_epoch_summary(
    epoch_id: str,
    db: AsyncSession = Depends(db_session),
    x_admin_key: str = Header(alias="X-Admin-Key")
):
    """
    Summary statistics for epoch allocation.
    
    - Total pool allocated
    - Number of affiliates paid
    - Payout status breakdown (completed, failed, pending)
    - Top earners
    - Total gross revenue
    """
```

#### 6.2 Payout Status Report

**File:** `services/affiliate-engine/src/app/main.py`

```python
@app.get("/admin/epochs/{epoch_id}/payout-status", response_model=PayoutStatusReport)
async def get_payout_status_report(
    epoch_id: str,
    db: AsyncSession = Depends(db_session),
    x_admin_key: str = Header(alias="X-Admin-Key")
):
    """
    Detailed payout status breakdown.
    
    Groups allocations by:
    - pending
    - processing
    - completed
    - failed
    
    Shows amounts and affiliate details for each group.
    """
```

---

## Implementation Timeline

| Phase | Component | Priority | Effort | Status |
|-------|-----------|----------|--------|--------|
| 1 | Projected Payout Endpoint | HIGH | 2 days | 🟡 Design Complete |
| 2 | Gross Revenue Calculation | HIGH | 3 days | ⚪ Not Started |
| 2.5 | MSME Payout Integration | HIGH | 3 days | ⚪ Not Started |
| 3 | Real-Time Ledger | MEDIUM | 2 days | ⚪ Not Started |
| 4 | Payment Flow Integration | HIGH | 4 days | ⚪ Not Started |
| 5 | Dashboard Enhancements | MEDIUM | 2 days | ⚪ Not Started |
| 6 | Admin Reporting | MEDIUM | 2 days | ⚪ Not Started |

---

## Database Migrations Required

1. **AffiliateTransaction table** - Ledger
2. **PoolAllocation schema updates** - Payout status fields
3. **Index on affiliate_id, epoch_id** - Query performance

---

## Service Integration Points

### Affiliate-Engine ↔ Payment-Revenue

- `GET /epoch/{epoch_id}/gross-revenue` - Fetch actual revenue
- `POST /payout/batch` - Request payout batch
- `POST /callbacks/payout-status` - Receive payout status

### Affiliate-Engine ↔ Audit-Service

- Emit events: `affiliate_payout_completed`, `affiliate_ledger_transaction`

---

## Testing Strategy

1. **Unit Tests** - Score calculation, tier qualification
2. **Integration Tests** - Payment-revenue integration, callback handling
3. **E2E Tests** - Full epoch flow: create → score → payout → callback
4. **Load Tests** - Projected payout calculation under load

---

## Success Metrics

- ✅ Affiliates see real-time projected earnings
- ✅ Actual payouts match projected amounts
- ✅ All transactions auditable via ledger
- ✅ Payout failures tracked and retryable
- ✅ <100ms response time for projected payout
- ✅ Zero revenue reconciliation discrepancies
