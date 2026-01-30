from __future__ import annotations

from typing import Any, Tuple

from ..oob_store import OOBStore


async def validate_items(*, store: OOBStore, session_id: str, event_id: str | None = None) -> Tuple[dict[str, Any], int]:
    """Ensure every cart item has a product reference and required options.

    This handler is intentionally ICE-free: it validates the OOB cart shape locally
    and records any per-line validation problems under `oob.meta.validation_problems`.
    """

    def _upd(oob: dict[str, Any]) -> dict[str, Any]:
        oob = dict(oob)
        cart = dict(oob.get("cart") or {})
        items = list(cart.get("items") or [])

        problems: list[dict[str, Any]] = []

        for idx, it in enumerate(items):
            if not isinstance(it, dict):
                problems.append({"index": idx, "error": "invalid_item"})
                continue

            # Require either product_id or sku
            if not it.get("product_id") and not it.get("sku"):
                problems.append({"index": idx, "error": "missing_product_ref", "product_name": it.get("product_name")})

            # If the item declares that options are required, ensure they exist
            if it.get("requires_options") and not it.get("options"):
                problems.append({"index": idx, "error": "missing_options"})

        if problems:
            meta = dict(oob.get("meta") or {})
            meta["validation_problems"] = problems
            oob["meta"] = meta
            oob["last_validation_error"] = "invalid_items"
            oob["last_node_executed"] = "order.validate_items"
            return oob

        # Passed validation: clear previous problems
        meta = dict(oob.get("meta") or {})
        meta.pop("validation_problems", None)
        oob["meta"] = meta
        oob.pop("last_validation_error", None)
        oob["last_node_executed"] = "order.validate_items"
        return oob

    return await store.cas_update(session_id, _upd)
