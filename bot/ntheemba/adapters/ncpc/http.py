"""HTTP adapter for the NCPC v1 published catalogue boundary."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from ntheemba.domain.product_resolution import ProductQuery
from ntheemba.ports.ncpc import CanonicalProduct


class NCPCIntegrationError(RuntimeError):
    """Safe base error for NCPC integration failures."""

    retryable = False


class NCPCUnavailableError(NCPCIntegrationError):
    """NCPC could not be reached within the configured transport policy."""

    retryable = True


class NCPCResponseError(NCPCIntegrationError):
    """NCPC returned a malformed or rejected response."""


class HttpNCPCAdapter:
    """Read only published canonical identity from the NCPC v1 HTTP API."""

    def __init__(
        self,
        *,
        base_url: str,
        bearer_token: str,
        timeout_seconds: float = 5.0,
        client: httpx.AsyncClient | None = None,
        allow_development_internal_ncpc: bool = False,
    ) -> None:
        url = base_url.strip().rstrip("/")
        parsed = urlparse(url)
        local_compose_ncpc = (
            allow_development_internal_ncpc and url == "http://ncpc:8080"
        )
        if not local_compose_ncpc and (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("NCPC base_url must be an absolute HTTPS endpoint")
        if not local_compose_ncpc:
            host = (parsed.hostname or "").strip().strip("[]").casefold()
            if host == "localhost" or host.endswith(".localhost"):
                raise ValueError("NCPC base_url must not target localhost")
            try:
                address = ip_address(host)
            except ValueError:
                address = None
            if address is not None and (
                address.is_private
                or address.is_loopback
                or address.is_link_local
                or address.is_multicast
                or address.is_reserved
                or address.is_unspecified
            ):
                raise ValueError("NCPC base_url must not target a non-public IP address")
        if not bearer_token.strip():
            raise ValueError("NCPC bearer_token must not be empty")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        self.base_url = url
        self._token = bearer_token
        self._timeout = timeout_seconds
        self._client = client

    async def search_products(
        self,
        query: ProductQuery,
        *,
        limit: int = 20,
    ) -> tuple[CanonicalProduct, ...]:
        params: dict[str, str | int] = {"limit": min(max(limit, 1), 50)}
        if query.barcode:
            params["barcode"] = query.barcode
        elif query.original_text:
            params["query"] = query.original_text
        data = await self._get("/v1/catalogue/candidates", params=params)
        candidates = data.get("candidates")
        if not isinstance(candidates, list):
            raise NCPCResponseError("NCPC candidate response is malformed")
        products: list[CanonicalProduct] = []
        for item in candidates:
            if not isinstance(item, dict):
                continue
            try:
                products.append(self._canonical(item))
            except NCPCResponseError:
                continue
        return tuple(products)

    async def get_product(self, product_id: str) -> CanonicalProduct | None:
        identity = product_id.strip()
        if not identity:
            raise ValueError("product_id must not be empty")
        try:
            data = await self._get(f"/v1/catalogue/variants/{identity}")
        except NCPCResponseError as error:
            if getattr(error, "code", "") == "NOT_FOUND":
                return None
            raise
        return self._canonical(data)

    async def resolve_barcode(self, barcode: str) -> CanonicalProduct | None:
        value = barcode.strip()
        if not value:
            raise ValueError("barcode must not be empty")
        data = await self._get(
            "/v1/catalogue/candidates",
            params={"barcode": value, "limit": 2},
        )
        candidates = data.get("candidates")
        if not isinstance(candidates, list):
            raise NCPCResponseError("NCPC barcode response is malformed")
        exact = [item for item in candidates if isinstance(item, dict)]
        if not exact:
            return None
        return self._canonical(exact[0])

    async def _get(
        self,
        path: str,
        *,
        params: dict[str, str | int] | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "X-Request-ID": f"ntheemba-{uuid4().hex}",
        }
        try:
            if self._client is not None:
                response = await self._client.get(
                    f"{self.base_url}{path}",
                    params=params,
                    headers=headers,
                    timeout=self._timeout,
                )
            else:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.get(
                        f"{self.base_url}{path}",
                        params=params,
                        headers=headers,
                    )
        except (httpx.TimeoutException, httpx.NetworkError) as error:
            raise NCPCUnavailableError("NCPC is temporarily unavailable") from error

        payload: Any
        try:
            payload = response.json()
        except ValueError as error:
            raise NCPCResponseError("NCPC returned a non-JSON response") from error
        if not isinstance(payload, dict):
            raise NCPCResponseError("NCPC response envelope is malformed")
        if response.status_code >= 500:
            raise NCPCUnavailableError("NCPC is temporarily unavailable")
        if response.status_code >= 400 or payload.get("success") is not True:
            details = payload.get("error") if isinstance(payload.get("error"), dict) else {}
            error = NCPCResponseError("NCPC rejected the request")
            error.code = str(details.get("code", "REQUEST_REJECTED"))  # type: ignore[attr-defined]
            raise error
        data = payload.get("data")
        if not isinstance(data, dict):
            raise NCPCResponseError("NCPC response data is malformed")
        return data

    @staticmethod
    def _canonical(item: dict[str, Any]) -> CanonicalProduct:
        product_id = str(item.get("ncpc_product_id", "")).strip()
        variant_id = str(item.get("ncpc_variant_id", "")).strip()
        name = str(item.get("canonical_name", "")).strip()
        if not product_id or not variant_id or not name:
            raise NCPCResponseError("NCPC candidate identity is incomplete")

        size_value: Decimal | None = None
        size_unit: str | None = None
        pack = item.get("pack_definition")
        if isinstance(pack, dict):
            measure = pack.get("primary_measure")
            if isinstance(measure, dict):
                raw_value = measure.get("value")
                raw_unit = str(measure.get("unit", "")).strip().lower()
                if raw_value is not None and raw_unit:
                    try:
                        candidate_value = Decimal(str(raw_value))
                    except (InvalidOperation, ValueError):
                        candidate_value = Decimal(0)
                    if candidate_value > 0:
                        size_value = candidate_value
                        size_unit = raw_unit

        identifiers = item.get("identifiers")
        barcode = None
        if isinstance(identifiers, list):
            barcode = next(
                (str(value).strip() for value in identifiers if str(value).strip()),
                None,
            )
        aliases = item.get("aliases")
        safe_aliases = tuple(
            str(value).strip()
            for value in aliases
            if str(value).strip()
        ) if isinstance(aliases, list) else ()

        return CanonicalProduct(
            product_id=product_id,
            variant_id=variant_id,
            canonical_name=name,
            brand=_optional_text(item.get("brand")),
            variant=_optional_text(item.get("variant_name")),
            size_value=size_value,
            size_unit=size_unit,
            barcode=barcode,
            category=_optional_text(item.get("category")),
            aliases=safe_aliases,
            catalogue_version=str(item.get("catalogue_version") or "unversioned"),
        )


def _optional_text(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None
