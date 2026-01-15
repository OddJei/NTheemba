from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import os

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


_DEFAULT_OP_WEIGHTS: Dict[str, float] = {
    "sales_volume": 0.5,
    "unique_buyers": 0.2,
    "msme_referrals": 0.2,
    "conversion_quality": 0.1,
}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return int(default)


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return float(default)


_OP_MIN_CLICKS = _env_int("AFFILIATE_OP_MIN_CLICKS", 30)
_OP_MIN_PAID_ATTRIBUTIONS = _env_int("AFFILIATE_OP_MIN_PAID_ATTRIBUTIONS", 3)
_OP_MIN_UNIQUE_BUYERS = _env_int("AFFILIATE_OP_MIN_UNIQUE_BUYERS", 3)
_OP_MIN_SALES_VOLUME = _env_float("AFFILIATE_OP_MIN_SALES_VOLUME", 500.0)


def _normalize_weights(weights: Optional[Dict[str, float]]) -> Dict[str, float]:
    if not weights:
        return dict(_DEFAULT_OP_WEIGHTS)

    # Backwards-compat: older configs used a direct "clicks" weight.
    # We interpret that as the weight for conversion quality (paid_attributions / clicks).
    w = dict(weights)
    if "conversion_quality" not in w and "clicks" in w:
        w["conversion_quality"] = float(w.get("clicks", 0.0))
    for k, v in _DEFAULT_OP_WEIGHTS.items():
        w.setdefault(k, float(v))
    return w


def _norm(value: float, max_value: float) -> float:
    if max_value <= 0.0:
        return 0.0
    if value <= 0.0:
        return 0.0
    return float(value) / float(max_value)


def _conversion_quality(clicks: int, paid_attributions: int, *, min_clicks: int = _OP_MIN_CLICKS) -> float:
    # Unique-number-only metric: paid orders per unique clickers.
    if int(clicks) < int(min_clicks):
        return 0.0
    return float(paid_attributions) / float(max(1, int(clicks)))


def _eligible_for_multiplier(m: AffiliateMetrics, *, min_clicks: int = _OP_MIN_CLICKS) -> bool:
    # Applies to both earned and purchased multipliers.
    return (
        int(m.clicks) >= int(min_clicks)
        and int(m.paid_attributions) >= int(_OP_MIN_PAID_ATTRIBUTIONS)
        and int(m.unique_buyers) >= int(_OP_MIN_UNIQUE_BUYERS)
        and float(m.sales_volume) >= float(_OP_MIN_SALES_VOLUME)
    )


async def get_or_create_settings(db: AsyncSession, *, pool_pct_default: float, epoch_days_default: int) -> CommissionSettings:
    settings = (await db.execute(select(CommissionSettings).where(CommissionSettings.id == 1))).scalar_one_or_none()
    if settings:
        # Lightweight upgrade path: ensure new OP weight keys exist without overwriting custom values.
        normalized = _normalize_weights(settings.weights)
        if normalized != (settings.weights or {}):
            settings.weights = normalized
            await db.commit()
        return settings

    settings = CommissionSettings(id=1, pool_pct=pool_pct_default, epoch_days=epoch_days_default)
    settings.weights = dict(_DEFAULT_OP_WEIGHTS)
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


def compute_op_scores(
    metrics: List[AffiliateMetrics],
    weights: Dict[str, float],
    *,
    min_clicks: int = _OP_MIN_CLICKS,
) -> tuple[Dict[str, float], Dict[str, dict]]:
    """Compute OP_final scores per affiliate.

    Uses max-normalized metrics per season epoch:
      OP_raw = wSV*(SV/SVmax) + wUB*(UB/UBmax) + wMR*(MR/MRmax) + wCQ*(CQ/CQmax)
      OP_final = OP_raw * multiplier

    Conversion quality is derived from existing unique-count metrics:
      CQ = paid_attributions / clicks (only if clicks >= min_clicks)
    """

    w = _normalize_weights(weights)

    cq_by_aff: Dict[str, float] = {
        m.affiliate_id: _conversion_quality(m.clicks, m.paid_attributions, min_clicks=min_clicks) for m in metrics
    }

    sales_max = max((float(m.sales_volume) for m in metrics), default=0.0)
    buyers_max = max((float(m.unique_buyers) for m in metrics), default=0.0)
    referrals_max = max((float(m.msme_referrals) for m in metrics), default=0.0)
    cq_max = max((float(cq) for cq in cq_by_aff.values()), default=0.0)

    scores: Dict[str, float] = {}
    details: Dict[str, dict] = {}
    for m in metrics:
        cq = float(cq_by_aff.get(m.affiliate_id, 0.0))
        op_raw = (
            float(w.get("sales_volume", 0.0)) * _norm(float(m.sales_volume), sales_max)
            + float(w.get("unique_buyers", 0.0)) * _norm(float(m.unique_buyers), buyers_max)
            + float(w.get("msme_referrals", 0.0)) * _norm(float(m.msme_referrals), referrals_max)
            + float(w.get("conversion_quality", 0.0)) * _norm(float(cq), cq_max)
        )

        eligible = _eligible_for_multiplier(m, min_clicks=min_clicks)
        effective_multiplier = float(m.tier_multiplier) if eligible else 1.0
        op_final = float(op_raw) * float(effective_multiplier)

        scores[m.affiliate_id] = float(op_final)
        details[m.affiliate_id] = {
            "op_raw": float(op_raw),
            "op_final": float(op_final),
            "conversion_quality": float(cq),
            "eligible_for_multiplier": bool(eligible),
            "effective_multiplier": float(effective_multiplier),
            "weights": {
                "sales_volume": float(w.get("sales_volume", 0.0)),
                "unique_buyers": float(w.get("unique_buyers", 0.0)),
                "msme_referrals": float(w.get("msme_referrals", 0.0)),
                "conversion_quality": float(w.get("conversion_quality", 0.0)),
            },
            "maxima": {
                "sales_volume": float(sales_max),
                "unique_buyers": float(buyers_max),
                "msme_referrals": float(referrals_max),
                "conversion_quality": float(cq_max),
            },
        }

    return scores, details


def compute_weighted_scores(metrics: List[AffiliateMetrics], weights: Dict[str, float]) -> Dict[str, float]:
    # Backwards-compatible wrapper: historically this returned "weighted_score".
    scores, _ = compute_op_scores(metrics, weights)
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
    scores, details = compute_op_scores(metrics, settings.weights)
    payouts = compute_payouts(scores, epoch.pool_amount_zmw)

    allocations: List[PoolAllocation] = []
    for m in metrics:
        d = details.get(m.affiliate_id, {})
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
                "conversion_quality": float(d.get("conversion_quality", 0.0)),
                "op_raw": float(d.get("op_raw", 0.0)),
                "op_final": float(d.get("op_final", 0.0)),
                "eligible_for_multiplier": bool(d.get("eligible_for_multiplier", False)),
                "effective_multiplier": float(d.get("effective_multiplier", 1.0)),
            },
            weighted_score=float(scores.get(m.affiliate_id, 0.0)),
            payout_zmw=float(payouts.get(m.affiliate_id, 0.0)),
        )
        db.add(alloc)
        allocations.append(alloc)

    await db.commit()
    return allocations
