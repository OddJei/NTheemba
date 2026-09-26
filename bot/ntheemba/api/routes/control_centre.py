"""Narrow local-only summary for the separate NDS Control Centre BFF."""

from __future__ import annotations

import hmac

from fastapi import APIRouter, HTTPException, Request

from ntheemba.api.routes.dev_storage import _runtime, integration_health

router = APIRouter(prefix="/control-centre", tags=["control-centre"], include_in_schema=False)


@router.get("/summary")
async def summary(request: Request) -> dict[str, object]:
    """Return only safe aggregate status; never developer diagnostics or channels."""
    settings = request.app.state.settings
    supplied = request.headers.get("x-nds-control-token", "")
    configured = settings.control_centre_token
    if (
        settings.environment not in {"development", "test"}
        or configured is None
        or not hmac.compare_digest(supplied, configured.get_secret_value())
    ):
        raise HTTPException(status_code=401, detail="unauthorized")
    runtime = _runtime(request)
    profiles = await runtime.business_registry.list_businesses()
    reader = await integration_health(request)
    return {
        "status": "ready",
        "ncpc_reader_status": str(dict(reader.get("ncpc", {})).get("status", "unavailable")),
        "businesses": [
            {
                "display_name": item.display_name,
                "adapter_type": item.adapter_type,
                "enabled": item.enabled,
            }
            for item in profiles
        ],
        "tradeflow": "not_connected",
    }
