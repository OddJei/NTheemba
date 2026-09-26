"""Admin-only fixture setup for the isolated Ntheemba/NCPC proof."""

from __future__ import annotations

import asyncio
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

NCPC_URL = os.environ.get("NCPC_PROOF_URL", "http://ncpc:8080").rstrip("/")
ADMIN_TOKEN = os.environ["NCPC_ADMIN_BOOTSTRAP_TOKEN"]


def _request(
    method: str, path: str, body: dict[str, object] | None = None
) -> tuple[int, dict[str, object]]:
    request = Request(
        f"{NCPC_URL}{path}",
        method=method,
        data=json.dumps(body).encode() if body else None,
        headers={
            "Authorization": f"Bearer {ADMIN_TOKEN}",
            "Content-Type": "application/json",
            "X-Request-ID": "nint-seed",
        },
    )
    try:
        with urlopen(request, timeout=15) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


def _data(result: tuple[int, dict[str, object]], expected: int) -> dict[str, object]:
    status, envelope = result
    assert status == expected and envelope.get("success") is True, envelope
    value = envelope.get("data")
    assert isinstance(value, dict), envelope
    return value


async def run() -> None:
    for _ in range(90):
        try:
            if _request("GET", "/health")[0] == 200:
                break
        except URLError:
            pass
        await asyncio.sleep(0.5)
    else:
        raise RuntimeError("NCPC did not become healthy")
    submission = _data(
        _request(
            "POST",
            "/v1/submissions/products",
            {
                "business_id": "nint-proof-business",
                "business_product_ref": "NINT-HTTP-001",
                "idempotency_key": "nint-http-proof-001",
                "canonical_name": "Ntheemba NCPC HTTP Proof Product",
                "variant_name": "Proof variant",
                "aliases": [{"text": "nint proof alias"}],
                "barcodes": [{"value": "0088888888882", "source": "synthetic_nint_proof"}],
                "source": "synthetic_nint_proof",
            },
        ),
        201,
    )
    approved = _data(
        _request(
            "POST",
            f"/v1/admin/reviews/{submission['review_id']}/decisions",
            {"outcome": "APPROVE_NEW", "rationale": "synthetic HTTP integration proof"},
        ),
        200,
    )
    _data(
        _request(
            "POST",
            "/v1/admin/publications",
            {"version": "NINT-HTTP-R1", "rationale": "synthetic HTTP integration proof"},
        ),
        201,
    )
    assert (approved["ncpc_product_id"], approved["ncpc_variant_id"]) == (
        "PRD-000001",
        "VAR-000001",
    )
    print("NTHEEMBA_NCPC_SYNTHETIC_FIXTURE_SEEDED")


if __name__ == "__main__":
    asyncio.run(run())
