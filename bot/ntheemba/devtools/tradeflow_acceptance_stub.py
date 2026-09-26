"""Local-only HTTPS TradeFlow v1 acceptance stub for Docker pipeline proof."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse

app = FastAPI(title="Ntheemba TradeFlow acceptance stub")


@dataclass(frozen=True, slots=True)
class AcceptanceBusiness:
    """One strictly tenant-bound local TradeFlow acceptance fixture."""

    business_id: str
    business_product_id: str
    business_name: str
    product_name: str
    selling_price: str
    order_id: str
    ncpc_product_id: str
    ncpc_variant_id: str
    availability_status: str

    @property
    def linked_identity(self) -> bool:
        return bool(self.ncpc_product_id and self.ncpc_variant_id)


def _business() -> AcceptanceBusiness:
    return AcceptanceBusiness(
        business_id=os.getenv("TRADEFLOW_ACCEPTANCE_BUSINESS_ID", "n24-acceptance-shop"),
        business_product_id=os.getenv("TRADEFLOW_ACCEPTANCE_PRODUCT_ID", "N24-LOCAL-RELISH"),
        business_name=os.getenv("TRADEFLOW_ACCEPTANCE_BUSINESS_NAME", "N24 Acceptance Shop"),
        product_name=os.getenv("TRADEFLOW_ACCEPTANCE_PRODUCT_NAME", "N24 Acceptance Local Relish"),
        selling_price=os.getenv("TRADEFLOW_ACCEPTANCE_SELLING_PRICE", "18.00"),
        order_id=os.getenv("TRADEFLOW_ACCEPTANCE_ORDER_ID", "ORD-N24-ACCEPTANCE"),
        ncpc_product_id=os.getenv("TRADEFLOW_ACCEPTANCE_NCPC_PRODUCT_ID", "").strip(),
        ncpc_variant_id=os.getenv("TRADEFLOW_ACCEPTANCE_NCPC_VARIANT_ID", "").strip(),
        availability_status=os.getenv("TRADEFLOW_ACCEPTANCE_AVAILABILITY", "in_stock").strip(),
    )


def _product(business: AcceptanceBusiness) -> dict[str, Any]:
    identity: dict[str, str] = {
        "status": "linked" if business.linked_identity else "awaiting_ncpc_review"
    }
    if business.linked_identity:
        identity.update(
            {
                "ncpc_prd_id": business.ncpc_product_id,
                "ncpc_var_id": business.ncpc_variant_id,
            }
        )
    return {
        "business_product_id": business.business_product_id,
        "business_id": business.business_id,
        "shop_id": "main",
        "name": business.product_name,
        "selling_price": business.selling_price,
        "currency": "ZMW",
        "availability": {"status": business.availability_status},
        "identity_status": identity["status"],
        "identity": identity,
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/exec")
async def exec_tradeflow(envelope: dict[str, Any]) -> JSONResponse:
    business = _business()
    expected_token = os.getenv("TRADEFLOW_ACCEPTANCE_TOKEN", "local-acceptance-token")
    if envelope.get("api_token") != expected_token:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"ok": False, "error": {"code": "INVALID_TOKEN"}},
        )
    if envelope.get("business_id") != business.business_id:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"ok": False, "error": {"code": "TENANT_MISMATCH"}},
        )

    action = str(envelope.get("action") or "")
    data: dict[str, Any] = envelope["data"] if isinstance(envelope.get("data"), dict) else {}
    query = str(data.get("query") or "").casefold()

    product = _product(business)
    if action == "catalogue.search" and "local relish" in query:
        return JSONResponse(content={"ok": True, "data": {"items": [product]}})
    if action == "catalogue.by_ncpc_variant":
        requested_variant = str(data.get("ncpc_variant_id") or "")
        matches_configured_identity = (
            business.linked_identity and requested_variant == business.ncpc_variant_id
        )
        items = [product] if matches_configured_identity else []
        return JSONResponse(content={"ok": True, "data": {"items": items}})
    if (
        action == "catalogue.item"
        and data.get("business_product_id") == business.business_product_id
    ):
        return JSONResponse(content={"ok": True, "data": {"item": product}})
    if action == "order.create":
        return JSONResponse(
            content={
                "ok": True,
                "data": {
                    "order": {
                        "order_id": business.order_id,
                        "status": "created",
                    },
                },
            }
        )
    if action == "business.profile":
        return JSONResponse(
            content={
                "ok": True,
                "data": {
                    "business_name": business.business_name,
                    "public_contact": {"phone": "+260970099024"},
                    "shops": [{"shop_id": "main", "primary": True, "location": "Lusaka"}],
                },
            }
        )

    return JSONResponse(content={"ok": True, "data": {"items": []}})
