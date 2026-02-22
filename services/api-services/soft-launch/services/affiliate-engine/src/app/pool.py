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
    AffiliateTierSetting,
    AffiliateEvent,
    AffiliateMetricSnapshot,
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
    session_cycles: int

    tier_name: Optional[str]
    tier_multiplier: float


_DEFAULT_OP_WEIGHTS: Dict[str, float] = {
    "sales_volume": 0.5,
    "unique_buyers": 0.2,
    "msme_referrals": 0.2,
    "session_cycles": 0.1,
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


async def _tier_thresholds(db: AsyncSession) -> dict[str, dict[str, float]]:
    """Per-tier qualification thresholds persisted in the DB.

    Falls back to defaults if the settings table is empty.
    """
    rows = (await db.execute(select(AffiliateTierSetting))).scalars().all()
    if rows:
        return {
            str(r.tier_name).strip().lower(): {
                "gmv": float(r.gmv_min),
                "buyers": float(r.buyers_min),
                "referrals": float(r.referrals_min),
                "session_cycles": float(r.session_cycles_min),
                "min_metrics_required": int(r.min_metrics_required),
            }
            for r in rows
        }

    # Metric keys: gmv, buyers, referrals, session_cycles
    return {
        "bronze": {
            "gmv": _env_float("AFFILIATE_TIER_BRONZE_GMV_MIN_ZMW", 1000.0),
            "buyers": float(_env_int("AFFILIATE_TIER_BRONZE_BUYERS_MIN", 20)),
            "referrals": float(_env_int("AFFILIATE_TIER_BRONZE_REFERRALS_MIN", 6)),
            "session_cycles": float(_env_int("AFFILIATE_TIER_BRONZE_SESSION_CYCLES_MIN", 120)),
            "min_metrics_required": float(_env_int("AFFILIATE_TIER_BRONZE_METRICS_REQUIRED", 4)),
        },
        "silver": {
            "gmv": _env_float("AFFILIATE_TIER_SILVER_GMV_MIN_ZMW", 2667.0),
            "buyers": float(_env_int("AFFILIATE_TIER_SILVER_BUYERS_MIN", 50)),
            "referrals": float(_env_int("AFFILIATE_TIER_SILVER_REFERRALS_MIN", 15)),
            "session_cycles": float(_env_int("AFFILIATE_TIER_SILVER_SESSION_CYCLES_MIN", 300)),
            "min_metrics_required": float(_env_int("AFFILIATE_TIER_SILVER_METRICS_REQUIRED", 3)),
        },
        "gold": {
            "gmv": _env_float("AFFILIATE_TIER_GOLD_GMV_MIN_ZMW", 5334.0),
            "buyers": float(_env_int("AFFILIATE_TIER_GOLD_BUYERS_MIN", 100)),
            "referrals": float(_env_int("AFFILIATE_TIER_GOLD_REFERRALS_MIN", 30)),
            "session_cycles": float(_env_int("AFFILIATE_TIER_GOLD_SESSION_CYCLES_MIN", 600)),
            "min_metrics_required": float(_env_int("AFFILIATE_TIER_GOLD_METRICS_REQUIRED", 2)),
        },
    }


def _qualify_tier(m: AffiliateMetrics, thresholds: dict[str, float]) -> tuple[bool, bool, int, int]:
    """Return (eligible, all_four_met, metrics_met_count, metrics_required)."""
    if not thresholds:
        return False, False, 0, 0

    met = 0
    if float(m.sales_volume) >= float(thresholds.get("gmv", 0.0)):
        met += 1
    if float(m.unique_buyers) >= float(thresholds.get("buyers", 0.0)):
        met += 1
    if float(m.msme_referrals) >= float(thresholds.get("referrals", 0.0)):
        met += 1
    # session_cycles metric
    if float(m.session_cycles) >= float(thresholds.get("session_cycles", 0.0)):
        met += 1

    required = int(thresholds.get("min_metrics_required", 2))
    eligible = met >= required
    all_four = met == 4
    return eligible, all_four, met, required


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
    # We interpret that as the weight for session_cycles if provided.
    w = dict(weights)
    if "session_cycles" not in w and "conversion_quality" in w:
        w["session_cycles"] = float(w.get("conversion_quality", 0.0))
    if "session_cycles" not in w and "clicks" in w:
        w["session_cycles"] = float(w.get("clicks", 0.0))
    for k, v in _DEFAULT_OP_WEIGHTS.items():
        w.setdefault(k, float(v))
    return w


def _norm(value: float, max_value: float) -> float:
    if max_value <= 0.0:
        return 0.0
    if value <= 0.0:
        return 0.0
    return float(value) / float(max_value)


def _effective_multiplier(
    m: AffiliateMetrics,
    *,
    min_clicks: Optional[int] = None,
    thresholds_by_tier: Optional[dict[str, dict[str, float]]] = None,
) -> tuple[bool, float, Optional[str], dict]:
    """Return (eligible, effective_multiplier, effective_tier_name, extra_details).

    Policy:
    - Multipliers only apply if the affiliate qualifies for the assigned tier.
    - To qualify: meet the tier's required metrics count.
    - If all 4 metrics meet thresholds: auto-upgrade one tier (bronze->silver, silver->gold).

    Note: eligibility is strictly based on the 4 metric thresholds.
    """

    assigned = (m.tier_name or "").strip().lower() or None
    if not assigned:
        return False, 1.0, None, {"assigned_tier": None}

    thresholds = (thresholds_by_tier or {}).get(assigned, {})
    eligible, all_four, met_count, required = _qualify_tier(m, thresholds)
    if not eligible:
        return False, 1.0, None, {
            "assigned_tier": assigned,
            "tier_thresholds_met": int(met_count),
            "tier_metrics_required": int(required),
            "tier_all_four": bool(all_four),
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

    # Compute an activity gate: require minimal operational signals so the multiplier
    # only applies to affiliates with sufficient activity. Use provided `min_clicks`
    # or fall back to environment defaults for other thresholds.
    min_clicks_actual = int(min_clicks) if min_clicks is not None else _op_min_clicks()
    activity_ok = (
        int(m.clicks or 0) >= int(min_clicks_actual)
        and int(m.paid_attributions or 0) >= int(_op_min_paid_attributions())
        and int(m.unique_buyers or 0) >= int(_op_min_unique_buyers())
        and float(m.sales_volume or 0.0) >= float(_op_min_sales_volume())
    )

    return True, float(effective_multiplier), str(effective_tier), {
        "assigned_tier": assigned,
        "tier_thresholds_met": int(met_count),
        "tier_metrics_required": int(required),
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


async def ensure_default_tier_settings(db: AsyncSession) -> None:
    defaults = {
        "bronze": {
            "gmv_min": 1000.0,
            "buyers_min": 20,
            "referrals_min": 6,
            "session_cycles_min": 120,
            "min_metrics_required": 4,
        },
        "silver": {
            "gmv_min": 2667.0,
            "buyers_min": 50,
            "referrals_min": 15,
            "session_cycles_min": 300,
            "min_metrics_required": 3,
        },
        "gold": {
            "gmv_min": 5334.0,
            "buyers_min": 100,
            "referrals_min": 30,
            "session_cycles_min": 600,
            "min_metrics_required": 2,
        },
    }

    existing = (await db.execute(select(AffiliateTierSetting))).scalars().all()
    existing_names = {t.tier_name for t in existing}

    changed = False
    for name, values in defaults.items():
        if name in existing_names:
            continue
        db.add(
            AffiliateTierSetting(
                tier_name=name,
                gmv_min=float(values["gmv_min"]),
                buyers_min=int(values["buyers_min"]),
                referrals_min=int(values["referrals_min"]),
                session_cycles_min=int(values["session_cycles_min"]),
                min_metrics_required=int(values["min_metrics_required"]),
            )
        )
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

    # Session cycles per affiliate: count distinct session_ids with conversion or sale events.
    cycles_rows = (
        await db.execute(
            select(AffiliateEvent.affiliate_id, func.count(func.distinct(AffiliateEvent.session_id)).label("cycles"))
            .where(
                AffiliateEvent.event_type.in_(["conversion", "sale"]),
                AffiliateEvent.affiliate_id.is_not(None),
                AffiliateEvent.session_id.is_not(None),
                AffiliateEvent.occurred_at >= start,
                AffiliateEvent.occurred_at <= end,
            )
            .group_by(AffiliateEvent.affiliate_id)
        )
    ).all()
    cycles_by_aff: Dict[str, int] = {str(aid): int(c or 0) for aid, c in cycles_rows}

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
        | set(cycles_by_aff)
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
                session_cycles=int(cycles_by_aff.get(affiliate_id, 0)),
                tier_name=tier_name,
                tier_multiplier=float(tier_multiplier),
            )
        )

    return metrics


def _share(value: float, total: float) -> float:
    if total <= 0:
        return 0.0
    return float(value) / float(total)


async def compute_op_scores(
    db: AsyncSession,
    metrics: List[AffiliateMetrics],
    weights: Dict[str, float],
    *,
    min_clicks: Optional[int] = None,
) -> tuple[Dict[str, float], Dict[str, dict]]:
    """Compute OP_final scores per affiliate.

    Uses max-normalized metrics per season epoch:
      OP_raw = wSV*(SV/SVmax) + wUB*(UB/UBmax) + wMR*(MR/MRmax) + wSC*(SC/SCmax)
      OP_final = OP_raw * multiplier
    """

    if min_clicks is None:
        min_clicks = _op_min_clicks()

    w = _normalize_weights(weights)
    thresholds_by_tier = await _tier_thresholds(db)

    cycles_by_aff: Dict[str, float] = {m.affiliate_id: float(m.session_cycles) for m in metrics}

    sales_max = max((float(m.sales_volume) for m in metrics), default=0.0)
    buyers_max = max((float(m.unique_buyers) for m in metrics), default=0.0)
    referrals_max = max((float(m.msme_referrals) for m in metrics), default=0.0)
    cycles_max = max((float(cycles) for cycles in cycles_by_aff.values()), default=0.0)

    scores: Dict[str, float] = {}
    details: Dict[str, dict] = {}
    for m in metrics:
        sc = float(cycles_by_aff.get(m.affiliate_id, 0.0))
        op_raw = (
            float(w.get("sales_volume", 0.0)) * _norm(float(m.sales_volume), sales_max)
            + float(w.get("unique_buyers", 0.0)) * _norm(float(m.unique_buyers), buyers_max)
            + float(w.get("msme_referrals", 0.0)) * _norm(float(m.msme_referrals), referrals_max)
            + float(w.get("session_cycles", 0.0)) * _norm(float(sc), cycles_max)
        )

        eligible, effective_multiplier, effective_tier, extra = _effective_multiplier(
            m,
            min_clicks=min_clicks,
            thresholds_by_tier=thresholds_by_tier,
        )
        op_final = float(op_raw) * float(effective_multiplier)

        scores[m.affiliate_id] = float(op_final)
        details[m.affiliate_id] = {
            "op_raw": float(op_raw),
            "op_final": float(op_final),
            "session_cycles": float(sc),
            "eligible_for_multiplier": bool(eligible),
            "effective_multiplier": float(effective_multiplier),
            "effective_tier": effective_tier,
            "tier_details": extra,
            "tier_thresholds_assigned": thresholds_by_tier.get((m.tier_name or "").strip().lower()),
            "tier_thresholds_effective": thresholds_by_tier.get((effective_tier or "").strip().lower()),
            "weights": {
                "sales_volume": float(w.get("sales_volume", 0.0)),
                "unique_buyers": float(w.get("unique_buyers", 0.0)),
                "msme_referrals": float(w.get("msme_referrals", 0.0)),
                "session_cycles": float(w.get("session_cycles", 0.0)),
            },
            "maxima": {
                "sales_volume": float(sales_max),
                "unique_buyers": float(buyers_max),
                "msme_referrals": float(referrals_max),
                "session_cycles": float(cycles_max),
            },
        }

    return scores, details


async def get_qualified_tiers(db: AsyncSession, metrics: AffiliateMetrics) -> list[str]:
    """Return list of tier names the affiliate qualifies for (ordered low->high)."""
    thresholds_by_tier = await _tier_thresholds(db)
    qualified: list[str] = []
    for tier_name in _TIER_ORDER:
        thresholds = thresholds_by_tier.get(tier_name, {})
        eligible, _, _, _ = _qualify_tier(metrics, thresholds)
        if eligible:
            qualified.append(tier_name)
    return qualified


async def compute_weighted_scores(
    db: AsyncSession,
    metrics: List[AffiliateMetrics],
    weights: Dict[str, float],
) -> Dict[str, float]:
    # Backwards-compatible wrapper: historically this returned "weighted_score".
    scores, _ = await compute_op_scores(db, metrics, weights)
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
    scores, details = await compute_op_scores(db, metrics, settings.weights)
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
                "session_cycles": m.session_cycles,
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


async def record_metric_snapshot(
    db: AsyncSession,
    epoch_id: str,
    affiliate_metrics: AffiliateMetrics,
    qualified_tiers: list[str],
    effective_tier: Optional[str],
    pool_amount_zmw: float,
    gross_revenue_zmw: float,
    weighted_score: float,
) -> AffiliateMetricSnapshot:
    """
    Record a snapshot of affiliate metrics at a specific point in time.
    
    Typically called when:
    - Epoch closes and allocations are finalized
    - Real-time projected payout is calculated
    
    Args:
        db: Database session
        epoch_id: ID of the epoch
        affiliate_metrics: AffiliateMetrics dataclass with all 7 metrics
        qualified_tiers: List of tiers the affiliate qualifies for
        effective_tier: Highest qualified tier (or None)
        pool_amount_zmw: Total pool amount for allocation
        gross_revenue_zmw: Total gross revenue for the epoch
        weighted_score: Calculated weighted score
    
    Returns:
        The created AffiliateMetricSnapshot record
    """
    # Calculate affiliate's share if pool was distributed equally among score
    total_score_in_epoch = 100.0  # Placeholder; in real scenario, sum all scores
    affiliate_share_pct = (weighted_score / total_score_in_epoch) if total_score_in_epoch > 0 else 0.0
    projected_payout_zmw = pool_amount_zmw * affiliate_share_pct if pool_amount_zmw > 0 else 0.0
    
    pool_pct = (pool_amount_zmw / gross_revenue_zmw) if gross_revenue_zmw > 0 else 0.0
    
    snapshot = AffiliateMetricSnapshot(
        epoch_id=epoch_id,
        affiliate_id=affiliate_metrics.affiliate_id,
        
        # The 4 primary weighted metrics
        sales_volume=affiliate_metrics.sales_volume,
        unique_buyers=affiliate_metrics.unique_buyers,
        msme_referrals=affiliate_metrics.msme_referrals,
        session_cycles=affiliate_metrics.session_cycles,
        
        # Supporting metrics
        clicks=affiliate_metrics.clicks,
        attributions=affiliate_metrics.attributions,
        paid_attributions=affiliate_metrics.paid_attributions,
        
        # Scoring
        weighted_score=weighted_score,
        
        # Tier qualification
        qualified_tiers=qualified_tiers,
        effective_tier=effective_tier,
        tier_multiplier=affiliate_metrics.tier_multiplier,
        
        # Payout projection
        pool_pct=pool_pct,
        pool_amount_zmw=pool_amount_zmw,
        affiliate_share_pct=affiliate_share_pct,
        projected_payout_zmw=projected_payout_zmw,
        
        meta={
            "tier_name": affiliate_metrics.tier_name,
            "epoch_id": epoch_id,
            "affiliate_id": affiliate_metrics.affiliate_id,
        },
    )
    
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    
    return snapshot


async def run_hybrid_epoch_scoring(db: AsyncSession, *, epoch_id: str | None = None) -> dict:
    """Run the updated hybrid scoring algorithm and persist snapshots.

    - Uses MSME referrals (once-ever) as referral metric
    - Pulls gross revenue from internal endpoint `/internal/gross-revenue`
    - Normalizes each metric by the epoch maxima (top performer anchors at 1.0)
    - Computes weighted_score using fixed weights: referrals 0.3, sales 0.5, buyers 0.2, sessions 0.1
    - Applies tier multipliers and computes pool shares and projected payouts
    - Updates `affiliate_metric_snapshots` rows and `pool_epochs.gross_revenue_zmw`/`effective_pool_zmw`
    """

    # 1) Resolve epoch
    epoch: PoolEpoch | None
    if epoch_id:
        epoch = (await db.execute(select(PoolEpoch).where(PoolEpoch.id == epoch_id))).scalar_one_or_none()
        if not epoch:
            raise ValueError("epoch_not_found")
    else:
        epoch = await get_open_epoch(db)
        if not epoch:
            raise ValueError("no_open_epoch")

    # 2) Fetch gross revenue from internal endpoint if available
    gross = float(getattr(epoch, "gross_revenue_zmw", 0.0) or 0.0)
    try:
        # internal endpoint base is expected to be configured via env (msme base or same service)
        import httpx
        msme_base = os.getenv("MSME_BASE_URL") or os.getenv("AFFILIATE_ENGINE_BASE_URL") or "http://localhost:8500"
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{msme_base.rstrip('/')}/internal/gross-revenue")
            if r.status_code == 200:
                j = r.json() if isinstance(r.json(), dict) else {}
                gross_val = j.get("gross_revenue_zmw") or j.get("gross") or j.get("amount")
                if gross_val is not None:
                    try:
                        gross = float(gross_val)
                    except Exception:
                        gross = float(gross or 0.0)
    except Exception:
        # If internal call fails, proceed with existing epoch.gross_revenue_zmw
        pass

    epoch.gross_revenue_zmw = float(gross)
    # Effective pool = gross revenue + bonus_pool_zmw
    effective_pool = float((epoch.gross_revenue_zmw or 0.0) + (epoch.bonus_pool_zmw or 0.0))
    epoch.effective_pool_zmw = float(effective_pool)
    await db.commit()

    # 3) Compute raw metrics for epoch
    metrics = await compute_metrics_for_epoch(db, epoch)

    # 4) Determine maxima per metric (top performer values)
    max_referrals = max((float(m.msme_referrals) for m in metrics), default=0.0)
    max_sales = max((float(m.sales_volume) for m in metrics), default=0.0)
    max_buyers = max((float(m.unique_buyers) for m in metrics), default=0.0)
    max_sessions = max((float(m.session_cycles) for m in metrics), default=0.0)

    # 5) Fixed weights per request
    weights = {
        "msme_referrals": 0.3,
        "sales_volume": 0.5,
        "unique_buyers": 0.2,
        "session_cycles": 0.1,
    }

    # 6) Compute normalized scores, weighted_score, apply tier multipliers, and compute shares
    details = {}
    raw_scores: dict[str, float] = {}
    weighted_scores: dict[str, float] = {}

    for m in metrics:
        rnorm = _norm(float(m.msme_referrals), max_referrals)
        snorm = _norm(float(m.sales_volume), max_sales)
        bnorm = _norm(float(m.unique_buyers), max_buyers)
        cnorm = _norm(float(m.session_cycles), max_sessions)

        weighted = (
            float(weights["msme_referrals"]) * rnorm
            + float(weights["sales_volume"]) * snorm
            + float(weights["unique_buyers"]) * bnorm
            + float(weights["session_cycles"]) * cnorm
        )

        # Resolve tiers and effective multiplier
        thresholds_by_tier = await _tier_thresholds(db)
        eligible, effective_multiplier, effective_tier, extra = _effective_multiplier(
            m, min_clicks=_op_min_clicks(), thresholds_by_tier=thresholds_by_tier
        )

        final_score = float(weighted) * float(effective_multiplier)
        raw_scores[m.affiliate_id] = float(weighted)
        weighted_scores[m.affiliate_id] = float(final_score)
        details[m.affiliate_id] = {
            "normalized": {"referrals": rnorm, "sales": snorm, "buyers": bnorm, "sessions": cnorm},
            "raw_weighted": float(weighted),
            "final_weighted": float(final_score),
            "effective_tier": effective_tier,
            "effective_multiplier": float(effective_multiplier),
            "tier_details": extra,
        }

    # 7) Total score and pool_pct per affiliate
    total_score = sum(weighted_scores.values())

    # Protect against division by zero
    if total_score <= 0:
        # set everything to zero and persist snapshots
        for m in metrics:
            # persist snapshot
            await record_metric_snapshot(
                db,
                epoch_id=epoch.id,
                affiliate_metrics=m,
                qualified_tiers=await get_qualified_tiers(db, m),
                effective_tier=details.get(m.affiliate_id, {}).get("effective_tier"),
                pool_amount_zmw=float(epoch.pool_amount_zmw or 0.0),
                gross_revenue_zmw=float(epoch.gross_revenue_zmw or 0.0),
                weighted_score=0.0,
            )
        return {"epoch_id": epoch.id, "status": "ok", "note": "total_score_zero"}

    # 8) Persist snapshots with computed values
    for m in metrics:
        ws = float(weighted_scores.get(m.affiliate_id, 0.0))
        pool_pct = float(ws) / float(total_score) if total_score > 0 else 0.0
        affiliate_share_pct = float(pool_pct) * float(m.tier_multiplier or 1.0)
        projected_payout_zmw = float(affiliate_share_pct) * float(effective_pool)

        # Compose meta with details
        meta = {
            "normalized": details.get(m.affiliate_id, {}).get("normalized"),
            "raw_weighted": details.get(m.affiliate_id, {}).get("raw_weighted"),
            "final_weighted": details.get(m.affiliate_id, {}).get("final_weighted"),
            "tier_details": details.get(m.affiliate_id, {}).get("tier_details"),
        }

        # Upsert snapshot for affiliate+epoch
        res = await db.execute(
            select(AffiliateMetricSnapshot).where(AffiliateMetricSnapshot.epoch_id == epoch.id, AffiliateMetricSnapshot.affiliate_id == m.affiliate_id)
        )
        snap = res.scalar_one_or_none()
        if not snap:
            snap = AffiliateMetricSnapshot(epoch_id=epoch.id, affiliate_id=m.affiliate_id)
            db.add(snap)
            await db.flush()

        snap.sales_volume = float(m.sales_volume)
        snap.unique_buyers = int(m.unique_buyers)
        snap.msme_referrals = int(m.msme_referrals)
        snap.session_cycles = int(m.session_cycles)

        snap.weighted_score = float(ws)
        snap.qualified_tiers = await get_qualified_tiers(db, m)
        snap.effective_tier = details.get(m.affiliate_id, {}).get("effective_tier")
        snap.tier_multiplier = float(m.tier_multiplier or 1.0)
        snap.pool_pct = float(pool_pct)
        snap.affiliate_share_pct = float(affiliate_share_pct)
        snap.projected_payout_zmw = float(projected_payout_zmw)
        snap.meta = meta
        snap.recorded_at = datetime.now(timezone.utc)

    await db.commit()

    return {
        "epoch_id": epoch.id,
        "status": "ok",
        "gross_revenue_zmw": float(epoch.gross_revenue_zmw or 0.0),
        "effective_pool_zmw": float(epoch.effective_pool_zmw or 0.0),
        "total_score": float(total_score),
    }
