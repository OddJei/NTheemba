from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.models import (
    AffiliateTier,
    AffiliateTierAssignment,
    AffiliateEvent,
    CommissionSettings,
    PoolAllocation,
    PoolEpoch,
)


@dataclass
class AffiliateMetrics:
    affiliate_id: str
    sales_volume: float
    unique_buyers: int
    msme_referrals: int

    # Clicks is defined as distinct buyer/user phones that clicked within the epoch.
    clicks: int
    attributions: int
    paid_attributions: int

    tier_name: Optional[str]
    tier_multiplier: float


async def get_or_create_settings(db: AsyncSession, *, pool_pct_default: float, epoch_days_default: int) -> CommissionSettings:
    settings = (await db.execute(select(CommissionSettings).where(CommissionSettings.id == 1))).scalar_one_or_none()
    if settings:
        return settings

    settings = CommissionSettings(id=1, pool_pct=pool_pct_default, epoch_days=epoch_days_default)
    db.add(settings)
    await db.commit()
    return settings


async def ensure_default_tiers(db: AsyncSession) -> None:
    defaults = {
        "bronze": (1.3, 200.0),
        "silver": (1.5, 700.0),
        "gold": (1.8, 1000.0),
    }

    existing = (await db.execute(select(AffiliateTier))).scalars().all()
    existing_names = {t.name for t in existing}

    changed = False
    for name, (mult, price) in defaults.items():
        if name in existing_names:
            continue
        db.add(AffiliateTier(name=name, multiplier=float(mult), price_zmw=float(price), active=True))
        changed = True

    if changed:
        await db.commit()


async def get_open_epoch(db: AsyncSession) -> Optional[PoolEpoch]:
    return (
        await db.execute(select(PoolEpoch).where(PoolEpoch.status == "open").order_by(PoolEpoch.starts_at.desc()))
    ).scalar_one_or_none()


async def get_or_open_epoch(db: AsyncSession, *, pool_pct: float, epoch_days: int) -> PoolEpoch:
    open_epoch = await get_open_epoch(db)
    if open_epoch:
        return open_epoch

    now = datetime.now(timezone.utc)
    epoch = PoolEpoch(starts_at=now, status="open", pool_pct=float(pool_pct), pool_amount_zmw=0.0)
    db.add(epoch)
    await db.commit()
    await db.refresh(epoch)
    return epoch


async def resolve_tier(db: AsyncSession, affiliate_id: str, as_of: datetime) -> Tuple[Optional[str], float]:
    q = (
        select(AffiliateTierAssignment)
        .where(
            AffiliateTierAssignment.affiliate_id == affiliate_id,
            AffiliateTierAssignment.starts_at <= as_of,
            (AffiliateTierAssignment.ends_at.is_(None) | (AffiliateTierAssignment.ends_at >= as_of)),
        )
        .order_by(AffiliateTierAssignment.starts_at.desc())
        .limit(1)
    )
    assignment = (await db.execute(q)).scalar_one_or_none()
    if not assignment:
        return None, 1.0

    tier = (await db.execute(select(AffiliateTier).where(AffiliateTier.name == assignment.tier_name))).scalar_one_or_none()
    if not tier or not tier.active:
        return assignment.tier_name, 1.0

    return tier.name, float(tier.multiplier)


async def compute_metrics_for_epoch(db: AsyncSession, epoch: PoolEpoch) -> List[AffiliateMetrics]:
    start = epoch.starts_at
    end = epoch.ends_at or datetime.now(timezone.utc)

    # Events-only: metrics are derived from affiliate_events.
    # event_type conventions:
    # - campaign_click: click tracked
    # - conversion: attribution created
    # - sale: payment success (affiliate commission amount recorded)

    # Sales volume (affiliate commission amount) per affiliate.
    sales_rows = (
        await db.execute(
            select(AffiliateEvent.affiliate_id, func.coalesce(func.sum(AffiliateEvent.amount_zmw), 0.0))
            .where(
                AffiliateEvent.event_type == "sale",
                AffiliateEvent.affiliate_id.is_not(None),
                AffiliateEvent.occurred_at >= start,
                AffiliateEvent.occurred_at <= end,
            )
            .group_by(AffiliateEvent.affiliate_id)
        )
    ).all()
    sales_by_aff = {str(aid): float(total or 0.0) for aid, total in sales_rows}

    # Clicks per affiliate: distinct phones that clicked.
    clicks_rows = (
        await db.execute(
            select(AffiliateEvent.affiliate_id, func.count(func.distinct(AffiliateEvent.buyer_phone)))
            .where(
                AffiliateEvent.event_type == "campaign_click",
                AffiliateEvent.affiliate_id.is_not(None),
                AffiliateEvent.buyer_phone.is_not(None),
                AffiliateEvent.occurred_at >= start,
                AffiliateEvent.occurred_at <= end,
            )
            .group_by(AffiliateEvent.affiliate_id)
        )
    ).all()
    clicks_by_aff = {str(aid): int(cnt or 0) for aid, cnt in clicks_rows}

    # Attributions per affiliate: distinct orders attributed.
    attr_rows = (
        await db.execute(
            select(AffiliateEvent.affiliate_id, func.count(func.distinct(AffiliateEvent.order_id)).label("attributions"))
            .where(
                AffiliateEvent.event_type == "conversion",
                AffiliateEvent.affiliate_id.is_not(None),
                AffiliateEvent.order_id.is_not(None),
                AffiliateEvent.occurred_at >= start,
                AffiliateEvent.occurred_at <= end,
            )
            .group_by(AffiliateEvent.affiliate_id)
        )
    ).all()
    attr_by_aff: Dict[str, int] = {str(aid): int(a or 0) for aid, a in attr_rows}

    # Paid attributions per affiliate: distinct paid orders (sales).
    paid_rows = (
        await db.execute(
            select(AffiliateEvent.affiliate_id, func.count(func.distinct(AffiliateEvent.order_id)).label("paid"))
            .where(
                AffiliateEvent.event_type == "sale",
                AffiliateEvent.affiliate_id.is_not(None),
                AffiliateEvent.order_id.is_not(None),
                AffiliateEvent.occurred_at >= start,
                AffiliateEvent.occurred_at <= end,
            )
            .group_by(AffiliateEvent.affiliate_id)
        )
    ).all()
    paid_by_aff: Dict[str, int] = {str(aid): int(p or 0) for aid, p in paid_rows}

    # Unique buyers and MSME referrals from paid (sale) events.
    buyers_rows = (
        await db.execute(
            select(
                AffiliateEvent.affiliate_id,
                func.count(func.distinct(AffiliateEvent.buyer_phone)).label("buyers"),
                func.count(func.distinct(AffiliateEvent.business_id)).label("msmes"),
            )
            .where(
                AffiliateEvent.event_type == "sale",
                AffiliateEvent.affiliate_id.is_not(None),
                AffiliateEvent.occurred_at >= start,
                AffiliateEvent.occurred_at <= end,
            )
            .group_by(AffiliateEvent.affiliate_id)
        )
    ).all()
    buyers_by_aff: Dict[str, Tuple[int, int]] = {str(aid): (int(b or 0), int(m or 0)) for aid, b, m in buyers_rows}

    all_affiliates = set(sales_by_aff) | set(clicks_by_aff) | set(attr_by_aff) | set(paid_by_aff) | set(buyers_by_aff)

    metrics: List[AffiliateMetrics] = []
    for affiliate_id in sorted(all_affiliates):
        attributions = int(attr_by_aff.get(affiliate_id, 0))
        paid_attributions = int(paid_by_aff.get(affiliate_id, 0))
        buyers, msmes = buyers_by_aff.get(affiliate_id, (0, 0))

        tier_name, tier_multiplier = await resolve_tier(db, affiliate_id, end)

        metrics.append(
            AffiliateMetrics(
                affiliate_id=affiliate_id,
                sales_volume=float(sales_by_aff.get(affiliate_id, 0.0)),
                unique_buyers=int(buyers),
                msme_referrals=int(msmes),
                clicks=int(clicks_by_aff.get(affiliate_id, 0)),
                attributions=int(attributions),
                paid_attributions=int(paid_attributions),
                tier_name=tier_name,
                tier_multiplier=float(tier_multiplier),
            )
        )

    return metrics


def _share(value: float, total: float) -> float:
    if total <= 0:
        return 0.0
    return float(value) / float(total)


def compute_weighted_scores(metrics: List[AffiliateMetrics], weights: Dict[str, float]) -> Dict[str, float]:
    totals = {
        "sales_volume": sum(m.sales_volume for m in metrics),
        "unique_buyers": sum(m.unique_buyers for m in metrics),
        "msme_referrals": sum(m.msme_referrals for m in metrics),
        "clicks": sum(m.clicks for m in metrics),
    }

    scores: Dict[str, float] = {}
    for m in metrics:
        score = (
            float(weights.get("sales_volume", 0.0)) * _share(m.sales_volume, totals["sales_volume"])
            + float(weights.get("unique_buyers", 0.0)) * _share(float(m.unique_buyers), totals["unique_buyers"])
            + float(weights.get("msme_referrals", 0.0)) * _share(float(m.msme_referrals), totals["msme_referrals"])
            + float(weights.get("clicks", 0.0)) * _share(float(m.clicks), totals["clicks"])
        )
        score *= float(m.tier_multiplier)
        scores[m.affiliate_id] = float(score)

    return scores


def compute_payouts(scores: Dict[str, float], pool_amount: float) -> Dict[str, float]:
    total_score = sum(scores.values())
    if total_score <= 0:
        return {aid: 0.0 for aid in scores}

    return {aid: float(pool_amount) * float(score) / float(total_score) for aid, score in scores.items()}


async def close_epoch_and_allocate(db: AsyncSession, epoch: PoolEpoch, settings: CommissionSettings) -> List[PoolAllocation]:
    # Close the epoch and compute allocations snapshot.
    epoch.ends_at = datetime.now(timezone.utc)
    epoch.status = "closed"
    epoch.pool_pct = float(settings.pool_pct)
    epoch.pool_amount_zmw = float(epoch.gross_revenue_zmw) * float(epoch.pool_pct)

    metrics = await compute_metrics_for_epoch(db, epoch)
    scores = compute_weighted_scores(metrics, settings.weights)
    payouts = compute_payouts(scores, epoch.pool_amount_zmw)

    allocations: List[PoolAllocation] = []
    for m in metrics:
        alloc = PoolAllocation(
            epoch_id=epoch.id,
            affiliate_id=m.affiliate_id,
            tier_name=m.tier_name,
            tier_multiplier=float(m.tier_multiplier),
            metrics={
                "sales_volume": m.sales_volume,
                "unique_buyers": m.unique_buyers,
                "msme_referrals": m.msme_referrals,
                "clicks": m.clicks,
                "attributions": m.attributions,
                "paid_attributions": m.paid_attributions,
            },
            weighted_score=float(scores.get(m.affiliate_id, 0.0)),
            payout_zmw=float(payouts.get(m.affiliate_id, 0.0)),
        )
        db.add(alloc)
        allocations.append(alloc)

    await db.commit()
    return allocations
