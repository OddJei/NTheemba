from __future__ import annotations

"""Canonical Redis key helpers.

These keys mirror the JSONB docs in `docs/bot_jsonb_examples.md` and
`docs/customer_jsonb_examples.md`.

Notes:
- Postgres is the source of truth; Redis keys are cache copies.
- Keys are intentionally stable; evolve via value `schema_version`.
"""


def bot_core(bot_id: str) -> str:
    return f"bot:core:{bot_id}"


def bot_by_phone(phone: str) -> str:
    return f"bot:by_phone:{phone}"


def bot_owner(owner_id: str) -> str:
    return f"bot:owner:{owner_id}"


def bot_config(bot_id: str) -> str:
    return f"bot:config:{bot_id}"


def bot_routing(bot_id: str) -> str:
    return f"bot:routing:{bot_id}"


def bot_policy(bot_id: str) -> str:
    return f"bot:policy:{bot_id}"


def bot_templates(bot_id: str, locale: str) -> str:
    return f"bot:templates:{bot_id}:{locale}"


def bot_flow(bot_id: str, flow_version: str) -> str:
    return f"bot:flow:{bot_id}:{flow_version}"


def bot_integrations(bot_id: str) -> str:
    return f"bot:integrations:{bot_id}"


def bot_kb(bot_id: str) -> str:
    return f"bot:kb:{bot_id}"


def bot_health(bot_id: str) -> str:
    return f"bot:health:{bot_id}"


def catalog_index(business_id: str) -> str:
    return f"bot:catalog:index:{business_id}"


def catalog_product(product_id: str) -> str:
    return f"bot:catalog:product:{product_id}"


def user_profile(user_id: str) -> str:
    return f"user:profile:{user_id}"


def user_by_phone(phone: str, business_id: str | None = None) -> str:
    if business_id:
        return f"user:by_phone:{business_id}:{phone}"
    return f"user:by_phone::{phone}"


def user_auth(user_id: str, business_id: str) -> str:
    return f"user:auth:{user_id}:{business_id}"


def user_prefs(user_id: str) -> str:
    return f"user:prefs:{user_id}"


def user_addresses(user_id: str) -> str:
    return f"user:addresses:{user_id}"


def user_bot_relationship(user_id: str, bot_id: str) -> str:
    return f"user:bot:{user_id}:{bot_id}"


def session_snapshot(session_id: str) -> str:
    return f"session:snapshot:{session_id}"


def session_context(session_id: str) -> str:
    return f"session:ctx:{session_id}"


def cart(cart_id: str) -> str:
    return f"cart:{cart_id}"


def order_draft(order_id: str) -> str:
    return f"order:draft:{order_id}"


def lock_hydrate(session_id: str) -> str:
    return f"lock:hydrate:{session_id}"


def neg_hydrate(session_id: str) -> str:
    return f"neg:hydrate:{session_id}"


def hydrated_ingress(session_id: str) -> str:
    """Cache key for full hydrated session blob from ICE (ingress)."""
    return f"hydrated:ingress:{session_id}"
