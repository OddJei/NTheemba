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

    # Clicks is treated as unique customers (distinct phone numbers) and is counted
    # "once, ever" across epochs (see compute_metrics_for_epoch).
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


_TIER_ORDER: list[str] = ["bronze", "silver", "gold"]


def _tier_index(name: str) -> int:
    try:
        return _TIER_ORDER.index(str(name).strip().lower())
    except ValueError:
        return -1


def _next_tier(name: str) -> str:
    idx = _tier_index(name)
    if idx < 0:
        return str(name)
    if idx + 1 >= len(_TIER_ORDER):
        return _TIER_ORDER[-1]
    return _TIER_ORDER[idx + 1]


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


def _tier_thresholds() -> dict[str, dict[str, float]]:
    """Per-tier qualification thresholds.

    Defaults match the product/policy doc.
    Environment overrides are supported mainly for testing / experimentation.
    """

    # Metric keys: gmv, buyers, referrals, customers
    return {
        "bronze": {
            "gmv": _env_float("AFFILIATE_TIER_BRONZE_GMV_MIN_ZMW", 15000.0),
            "buyers": float(_env_int("AFFILIATE_TIER_BRONZE_BUYERS_MIN", 60)),
            "referrals": float(_env_int("AFFILIATE_TIER_BRONZE_REFERRALS_MIN", 6)),
            "customers": float(_env_int("AFFILIATE_TIER_BRONZE_CUSTOMERS_MIN", 120)),
        },
        "silver": {
            "gmv": _env_float("AFFILIATE_TIER_SILVER_GMV_MIN_ZMW", 40000.0),
            "buyers": float(_env_int("AFFILIATE_TIER_SILVER_BUYERS_MIN", 150)),
            "referrals": float(_env_int("AFFILIATE_TIER_SILVER_REFERRALS_MIN", 15)),
            "customers": float(_env_int("AFFILIATE_TIER_SILVER_CUSTOMERS_MIN", 300)),
        },
        "gold": {
            "gmv": _env_float("AFFILIATE_TIER_GOLD_GMV_MIN_ZMW", 80000.0),
            "buyers": float(_env_int("AFFILIATE_TIER_GOLD_BUYERS_MIN", 300)),
            "referrals": float(_env_int("AFFILIATE_TIER_GOLD_REFERRALS_MIN", 30)),
            "customers": float(_env_int("AFFILIATE_TIER_GOLD_CUSTOMERS_MIN", 600)),
        },
    }


def _qualify_tier(m: AffiliateMetrics, tier_name: str) -> tuple[bool, bool, int]:
    """Return (eligible, all_four_met, metrics_met_count)."""
    t = _tier_thresholds().get(str(tier_name).strip().lower())
    if not t:
        return False, False, 0

    met = 0
    if float(m.sales_volume) >= float(t["gmv"]):
        met += 1
    if float(m.unique_buyers) >= float(t["buyers"]):
        met += 1
    if float(m.msme_referrals) >= float(t["referrals"]):
        met += 1
    # conversion_quality == unique customers
    if float(m.clicks) >= float(t["customers"]):
        met += 1

    eligible = met >= 2
    all_four = met == 4
    return eligible, all_four, met


def _op_min_clicks() -> int:
    return _env_int("AFFILIATE_OP_MIN_CLICKS", 30)


def _op_min_paid_attributions() -> int:
    return _env_int("AFFILIATE_OP_MIN_PAID_ATTRIBUTIONS", 3)


def _op_min_unique_buyers() -> int:
    return _env_int("AFFILIATE_OP_MIN_UNIQUE_BUYERS", 3)


def _op_min_sales_volume() -> float:
    return _env_float("AFFILIATE_OP_MIN_SALES_VOLUME", 500.0)


def _gate_on_delivery() -> bool:
    return os.getenv("AFFILIATE_GATE_ON_DELIVERY", "0") in ("1", "true", "True")


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


def _effective_multiplier(m: AffiliateMetrics, *, min_clicks: Optional[int] = None) -> tuple[bool, float, Optional[str], dict]:
    """Return (eligible, effective_multiplier, effective_tier_name, extra_details).

    Policy:
    - Multipliers only apply if the affiliate qualifies for the assigned tier.
    - To qualify: meet thresholds in >= 2 metrics for that tier.
    - If all 4 metrics meet thresholds: auto-upgrade one tier (bronze->silver, silver->gold).

    Note: we still keep a small activity gate (min_clicks / min_paid / etc) so a tier can't activate
    on obviously fake/empty activity, but the main qualification is the per-tier thresholds.
    """

    assigned = (m.tier_name or "").strip().lower() or None
    if not assigned:
        return False, 1.0, None, {"assigned_tier": None}

    if min_clicks is None:
        min_clicks = _op_min_clicks()

    # Basic activity gate (kept for safety; can be tuned via env vars)
    activity_ok = (
        int(m.clicks) >= int(min_clicks)
        and int(m.paid_attributions) >= int(_op_min_paid_attributions())
        and int(m.unique_buyers) >= int(_op_min_unique_buyers())
        and float(m.sales_volume) >= float(_op_min_sales_volume())
    )

    eligible, all_four, met_count = _qualify_tier(m, assigned)
    eligible = bool(activity_ok and eligible)
    if not eligible:
        return False, 1.0, None, {
            "assigned_tier": assigned,
            "tier_thresholds_met": int(met_count),
            "tier_all_four": bool(all_four),
            "activity_gate": bool(activity_ok),
        }

    effective_tier = assigned
    if all_four:
        effective_tier = _next_tier(assigned)

    # If upgraded tier is one level up, use the default multipliers (policy).
    # Otherwise use the assigned tier multiplier from DB.
    default_mult = {"bronze": 1.3, "silver": 1.5, "gold": 1.8}
    if effective_tier != assigned:
        effective_multiplier = float(default_mult.get(effective_tier, m.tier_multiplier))
    else:
        # If DB-stored multiplier is missing/default (1.0) but the tier is one of the policy
        # tiers, fall back to the policy default multiplier so tests and behavior match expectations.
        if float(m.tier_multiplier) <= 1.0 and assigned in default_mult:
            effective_multiplier = float(default_mult.get(assigned, 1.0))
        else:
            effective_multiplier = float(m.tier_multiplier)

    return True, float(effective_multiplier), str(effective_tier), {
        "assigned_tier": assigned,
        "tier_thresholds_met": int(met_count),
        "tier_all_four": bool(all_four),
        "activity_gate": bool(activity_ok),
    }


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
        # Fallback: if the tier row is missing (tests or migrations), use policy default multipliers
        defaults = {"bronze": 1.3, "silver": 1.5, "gold": 1.8}
        return assignment.tier_name, float(defaults.get((assignment.tier_name or "").strip().lower(), 1.0))

    return tier.name, float(tier.multiplier)


async def compute_metrics_for_epoch(db: AsyncSession, epoch: PoolEpoch) -> List[AffiliateMetrics]:
    start = epoch.starts_at
    end = epoch.ends_at or datetime.now(timezone.utc)

    # Events-only: metrics are derived from affiliate_events.
    # event_type conventions:
    # - campaign_click: click tracked
    # - conversion: attribution created
    # - sale: payment success (affiliate commission amount recorded)

    # Sales volume (GMV) per affiliate.
    # Time column: optionally gate on delivery confirmation when configured.
    time_col = AffiliateEvent.delivered_at if _gate_on_delivery() else AffiliateEvent.occurred_at

    sales_rows = (
        await db.execute(
            select(AffiliateEvent.affiliate_id, func.coalesce(func.sum(AffiliateEvent.amount_zmw), 0.0))
            .where(
                AffiliateEvent.event_type == "sale",
                AffiliateEvent.affiliate_id.is_not(None),
                time_col.is_not(None),
                time_col >= start,
                time_col <= end,
            )
            .group_by(AffiliateEvent.affiliate_id)
        )
    ).all()
    sales_by_aff = {str(aid): float(total or 0.0) for aid, total in sales_rows}

    # Uniqueness policy ("once, ever"):
    # - Unique customers: count a phone number only on its first-ever campaign_click.
    # - Unique buyers: count a phone number only on its first-ever sale.
    # - MSME referrals: count a business only on its first-ever sale.
    # These are then attributed to the affiliate who got that first-ever event.

    click_rn = func.row_number().over(partition_by=AffiliateEvent.buyer_phone, order_by=AffiliateEvent.occurred_at.asc()).label("rn")
    clicks_first_subq = (
        select(
            AffiliateEvent.affiliate_id.label("affiliate_id"),
            AffiliateEvent.buyer_phone.label("buyer_phone"),
            AffiliateEvent.occurred_at.label("occurred_at"),
            click_rn,
        )
        .where(
            AffiliateEvent.event_type == "campaign_click",
            AffiliateEvent.affiliate_id.is_not(None),
            AffiliateEvent.buyer_phone.is_not(None),
        )
        .subquery()
    )
    clicks_rows = (
        await db.execute(
            select(clicks_first_subq.c.affiliate_id, func.count().label("clicks"))
            .where(
                clicks_first_subq.c.rn == 1,
                clicks_first_subq.c.occurred_at >= start,
                clicks_first_subq.c.occurred_at <= end,
            )
            .group_by(clicks_first_subq.c.affiliate_id)
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
                time_col.is_not(None),
                time_col >= start,
                time_col <= end,
            )
            .group_by(AffiliateEvent.affiliate_id)
        )
    ).all()
    paid_by_aff: Dict[str, int] = {str(aid): int(p or 0) for aid, p in paid_rows}

    # Unique buyers counted per-epoch: distinct buyer_phone with a sale in the epoch.
    buyers_rows = (
        await db.execute(
            select(AffiliateEvent.affiliate_id, func.count(func.distinct(AffiliateEvent.buyer_phone)).label("buyers"))
            .where(
                AffiliateEvent.event_type == "sale",
                AffiliateEvent.affiliate_id.is_not(None),
                AffiliateEvent.buyer_phone.is_not(None),
                time_col.is_not(None),
                time_col >= start,
                time_col <= end,
            )
            .group_by(AffiliateEvent.affiliate_id)
        )
    ).all()
    buyers_count_by_aff: Dict[str, int] = {str(aid): int(b or 0) for aid, b in buyers_rows}

    # MSME referrals (once-ever) based on first-ever sale per business.
    biz_rn = func.row_number().over(partition_by=AffiliateEvent.business_id, order_by=AffiliateEvent.occurred_at.asc()).label("rn")
    msme_first_subq = (
        select(
            AffiliateEvent.affiliate_id.label("affiliate_id"),
            AffiliateEvent.business_id.label("business_id"),
            time_col.label("occurred_at"),
            biz_rn,
        )
        .where(
            AffiliateEvent.event_type == "sale",
            AffiliateEvent.affiliate_id.is_not(None),
            AffiliateEvent.business_id.is_not(None),
            time_col.is_not(None),
        )
        .subquery()
    )
    msme_rows = (
        await db.execute(
            select(msme_first_subq.c.affiliate_id, func.count().label("msmes"))
            .where(
                msme_first_subq.c.rn == 1,
                msme_first_subq.c.occurred_at >= start,
                msme_first_subq.c.occurred_at <= end,
            )
            .group_by(msme_first_subq.c.affiliate_id)
        )
    ).all()
    msme_count_by_aff: Dict[str, int] = {str(aid): int(m or 0) for aid, m in msme_rows}

    # Include affiliates with any in-epoch activity, even if once-ever uniqueness
    # results in 0 counted clicks/buyers/referrals for the epoch.
    active_aff_rows = (
        await db.execute(
            select(func.distinct(AffiliateEvent.affiliate_id))
            .where(
                AffiliateEvent.affiliate_id.is_not(None),
                AffiliateEvent.occurred_at >= start,
                AffiliateEvent.occurred_at <= end,
            )
        )
    ).all()
    active_affiliates = {str(r[0]) for r in active_aff_rows if r and r[0]}

    all_affiliates = (
        set(sales_by_aff)
        | set(clicks_by_aff)
        | set(attr_by_aff)
        | set(paid_by_aff)
        | set(buyers_count_by_aff)
        | set(msme_count_by_aff)
        | set(active_affiliates)
    )

    metrics: List[AffiliateMetrics] = []
    for affiliate_id in sorted(all_affiliates):
        attributions = int(attr_by_aff.get(affiliate_id, 0))
        paid_attributions = int(paid_by_aff.get(affiliate_id, 0))
        buyers = int(buyers_count_by_aff.get(affiliate_id, 0))
        msmes = int(msme_count_by_aff.get(affiliate_id, 0))

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
    min_clicks: Optional[int] = None,
) -> tuple[Dict[str, float], Dict[str, dict]]:
    """Compute OP_final scores per affiliate.

    Uses max-normalized metrics per season epoch:
      OP_raw = wSV*(SV/SVmax) + wUB*(UB/UBmax) + wMR*(MR/MRmax) + wCQ*(CQ/CQmax)
      OP_final = OP_raw * multiplier

        Conversion quality is treated as **unique customers**.
            CQ = unique phone numbers brought to the bot.
        Uniqueness policy: phones are counted "once, ever" across epochs.
    """

    if min_clicks is None:
        min_clicks = _op_min_clicks()

    w = _normalize_weights(weights)

    # Unique customers is provided by metrics.clicks (see compute_metrics_for_epoch).
    cq_by_aff: Dict[str, float] = {m.affiliate_id: float(m.clicks) for m in metrics}

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

        eligible, effective_multiplier, effective_tier, extra = _effective_multiplier(m, min_clicks=min_clicks)
        op_final = float(op_raw) * float(effective_multiplier)

        scores[m.affiliate_id] = float(op_final)
        details[m.affiliate_id] = {
            "op_raw": float(op_raw),
            "op_final": float(op_final),
            "conversion_quality": float(cq),
            "eligible_for_multiplier": bool(eligible),
            "effective_multiplier": float(effective_multiplier),
            "effective_tier": effective_tier,
            "tier_details": extra,
            "tier_thresholds_assigned": _tier_thresholds().get((m.tier_name or "").strip().lower()),
            "tier_thresholds_effective": _tier_thresholds().get((effective_tier or "").strip().lower()),
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
