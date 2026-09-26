"""Tenant-bound HTTP adapter for the Standard TradeFlow public v1 boundary."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import secrets
import socket
import time
from datetime import date, datetime, time as clock_time
from decimal import Decimal, InvalidOperation
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from ntheemba.domain.booking_draft import AppointmentSlot, ServiceSelection
from ntheemba.domain.customers import LoyaltyStatus, MinimalBusinessClient
from ntheemba.domain.enums import FulfilmentMethod
from ntheemba.ports.tradeflow import (
    BookingSubmissionRequest,
    BusinessHours,
    BusinessInformation,
    BusinessProduct,
    FAQAnswer,
    MinimalClientCreateRequest,
    OrderSubmissionRequest,
    ProductAvailability,
    StaffOption,
    SubmissionResult,
)


class TradeFlowIntegrationError(RuntimeError):
    """Safe base error for TradeFlow integration failures."""

    retryable = False


class TradeFlowUnavailableError(TradeFlowIntegrationError):
    """The configured tenant TradeFlow endpoint could not be reached safely."""

    retryable = True


class TradeFlowResponseError(TradeFlowIntegrationError):
    """TradeFlow rejected a request or returned a malformed envelope."""

    def __init__(self, message: str, *, code: str = "REQUEST_REJECTED") -> None:
        super().__init__(message)
        self.code = code


class TradeFlowFeatureUnavailableError(TradeFlowIntegrationError):
    """The selected TradeFlow edition does not expose the requested capability."""


class HttpTradeFlowAdapter:
    """Call one exact tenant TradeFlow deployment through its public v1 API."""

    def __init__(
        self,
        *,
        business_id: str,
        base_url: str,
        api_token: str,
        default_shop_id: str = "",
        signing_secret: str | None = None,
        timeout_seconds: float = 7.0,
        client: httpx.AsyncClient | None = None,
        verify_tls: bool = True,
        allow_private_destination_hosts: frozenset[str] = frozenset(),
    ) -> None:
        business = business_id.strip()
        url = base_url.strip().rstrip("/")
        if not business:
            raise ValueError("business_id must not be empty")
        if not url.startswith("https://"):
            raise ValueError("TradeFlow base_url must use HTTPS")
        parsed_url = urlparse(url)
        if not parsed_url.hostname:
            raise ValueError("TradeFlow base_url must include a hostname")
        if not api_token.strip():
            raise ValueError("TradeFlow api_token must not be empty")
        if signing_secret is not None and len(signing_secret) < 24:
            raise ValueError("TradeFlow signing_secret must be at least 24 characters")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        self.business_id = business
        self.base_url = url
        self._api_token = api_token
        self.default_shop_id = default_shop_id.strip()
        self._signing_secret = signing_secret
        self._timeout = timeout_seconds
        self._client = client
        self._verify_tls = verify_tls
        self._destination_host = parsed_url.hostname.strip().strip("[]").casefold()
        self._destination_port = parsed_url.port or 443
        self._allow_private_destination_hosts = frozenset(
            item.strip().casefold() for item in allow_private_destination_hosts if item.strip()
        )

    async def get_business_information(self, business_id: str) -> BusinessInformation:
        self._assert_business(business_id)
        data = await self._request("business.profile", {})
        contact = data.get("public_contact") if isinstance(data.get("public_contact"), dict) else {}
        shops = data.get("shops") if isinstance(data.get("shops"), list) else []
        primary = next(
            (shop for shop in shops if isinstance(shop, dict) and shop.get("primary") is True),
            shops[0] if shops and isinstance(shops[0], dict) else {},
        )
        location = ""
        if isinstance(primary, dict):
            raw_location = primary.get("location")
            if isinstance(raw_location, str):
                location = raw_location.strip()
            elif isinstance(raw_location, dict):
                location = ", ".join(
                    str(value).strip()
                    for value in raw_location.values()
                    if str(value).strip()
                )
        return BusinessInformation(
            business_id=self.business_id,
            name=str(data.get("business_name") or self.business_id),
            description=str(data.get("description") or ""),
            location=location or str(contact.get("address") or ""),
            contact_phone=str(contact.get("whatsapp") or contact.get("phone") or ""),
            currency=str(data.get("currency") or "ZMW"),
        )

    async def get_business_hours(
        self,
        business_id: str,
        *,
        at: datetime,
    ) -> BusinessHours:
        self._assert_business(business_id)
        data = await self._request(
            "business.hours",
            self._shop_data(),
        )
        rows = data.get("hours") if isinstance(data.get("hours"), list) else []
        weekday = at.strftime("%A").casefold()
        row = next(
            (
                item
                for item in rows
                if isinstance(item, dict)
                and str(item.get("day", "")).strip().casefold() == weekday
            ),
            None,
        )
        if row is None or row.get("closed") is True:
            return BusinessHours(is_open=False, local_date=at.date(), special_closure=row is not None)
        opens = _parse_clock(row.get("open"))
        closes = _parse_clock(row.get("close"))
        if opens is None or closes is None:
            return BusinessHours(is_open=False, local_date=at.date(), note="hours unavailable")
        local_clock = at.timetz().replace(tzinfo=None)
        return BusinessHours(
            is_open=opens <= local_clock < closes,
            local_date=at.date(),
            opens_at=opens,
            closes_at=closes,
        )

    async def search_faqs(
        self,
        business_id: str,
        query: str,
        *,
        limit: int = 5,
    ) -> tuple[FAQAnswer, ...]:
        del query, limit
        self._assert_business(business_id)
        raise TradeFlowFeatureUnavailableError("Standard TradeFlow does not expose FAQ search yet")

    async def filter_business_products(
        self,
        business_id: str,
        ncpc_variant_ids: tuple[str, ...],
    ) -> tuple[BusinessProduct, ...]:
        self._assert_business(business_id)
        if len(ncpc_variant_ids) > 50:
            raise ValueError("ncpc_variant_ids must not exceed 50 items")
        products: list[BusinessProduct] = []
        seen: set[tuple[str, str]] = set()
        for variant_id in ncpc_variant_ids:
            variant = variant_id.strip()
            if not variant:
                continue
            data = await self._request(
                "catalogue.by_ncpc_variant",
                self._shop_data(ncpc_variant_id=variant),
            )
            items = data.get("items") if isinstance(data.get("items"), list) else []
            for item in items:
                if not isinstance(item, dict):
                    continue
                product = self._product(item, require_canonical=True)
                identity = (str(item.get("shop_id") or self.default_shop_id), product.business_product_id)
                if identity not in seen:
                    seen.add(identity)
                    products.append(product)
        return tuple(products)

    async def get_business_product(
        self,
        business_id: str,
        business_product_id: str,
    ) -> BusinessProduct | None:
        self._assert_business(business_id)
        try:
            data = await self._request(
                "catalogue.item",
                self._shop_data(business_product_id=business_product_id),
            )
        except TradeFlowResponseError as error:
            if error.code == "PRODUCT_NOT_FOUND":
                return None
            raise
        item = data.get("item")
        if not isinstance(item, dict):
            raise TradeFlowResponseError("TradeFlow product response is malformed")
        return self._product(item, require_canonical=False)

    async def search_services(
        self,
        business_id: str,
        query: str,
        *,
        limit: int = 20,
    ) -> tuple[ServiceSelection, ...]:
        del query, limit
        self._assert_business(business_id)
        raise TradeFlowFeatureUnavailableError("Standard TradeFlow does not expose services")

    async def get_service(self, business_id: str, service_id: str) -> ServiceSelection | None:
        del service_id
        self._assert_business(business_id)
        raise TradeFlowFeatureUnavailableError("Standard TradeFlow does not expose services")

    async def find_client_by_phone(
        self,
        business_id: str,
        phone_e164: str,
    ) -> MinimalBusinessClient | None:
        del phone_e164
        self._assert_business(business_id)
        raise TradeFlowFeatureUnavailableError("Standard TradeFlow does not expose client lookup")

    async def create_minimal_client(
        self,
        business_id: str,
        request: MinimalClientCreateRequest,
        *,
        idempotency_key: str,
    ) -> MinimalBusinessClient:
        del request, idempotency_key
        self._assert_business(business_id)
        raise TradeFlowFeatureUnavailableError("Standard TradeFlow does not expose client creation")

    async def get_loyalty_status(
        self,
        business_id: str,
        client_id: str,
    ) -> LoyaltyStatus | None:
        del client_id
        self._assert_business(business_id)
        raise TradeFlowFeatureUnavailableError("Standard TradeFlow does not expose loyalty")

    async def check_product_availability(
        self,
        business_id: str,
        business_product_id: str,
        *,
        quantity: int,
        shop_id: str = "",
    ) -> ProductAvailability:
        self._assert_business(business_id)
        try:
            data = await self._request(
                "catalogue.item",
                self._shop_data(shop_id=shop_id, business_product_id=business_product_id),
            )
        except TradeFlowResponseError as error:
            if error.code != "PRODUCT_NOT_FOUND":
                raise
            data = {}
        item = data.get("item") if isinstance(data, dict) else None
        product = self._product(item, require_canonical=False) if isinstance(item, dict) else None
        if product is None:
            return ProductAvailability(
                business_product_id=business_product_id,
                requested_quantity=quantity,
                available_quantity=0,
                selling_price=Decimal("0"),
                currency="ZMW",
                public_visible=False,
                shop_id=shop_id,
            )
        # v1 exposes only in/out classification, not exact stock.  Returning one unit
        # when in stock is deliberately conservative: quantity > 1 cannot be falsely
        # confirmed until TradeFlow exposes a quantity-safe validation contract.
        return ProductAvailability(
            business_product_id=business_product_id,
            requested_quantity=quantity,
            available_quantity=1 if product.available else 0,
            selling_price=product.selling_price,
            currency=product.currency,
            public_visible=product.public_visible,
            shop_id=shop_id or product.shop_id,
        )

    async def get_available_slots(
        self,
        business_id: str,
        service_id: str,
        *,
        appointment_date: date,
    ) -> tuple[AppointmentSlot, ...]:
        del service_id, appointment_date
        self._assert_business(business_id)
        raise TradeFlowFeatureUnavailableError("Standard TradeFlow does not expose booking")

    async def get_qualified_staff(
        self,
        business_id: str,
        service_id: str,
        *,
        appointment_date: date,
        start_time: clock_time,
    ) -> tuple[StaffOption, ...]:
        del service_id, appointment_date, start_time
        self._assert_business(business_id)
        raise TradeFlowFeatureUnavailableError("Standard TradeFlow does not expose booking")

    async def create_order_request(
        self,
        business_id: str,
        request: OrderSubmissionRequest,
        *,
        idempotency_key: str,
    ) -> SubmissionResult:
        self._assert_business(business_id)
        if request.fulfilment_method == FulfilmentMethod.DELIVERY:
            raise TradeFlowFeatureUnavailableError(
                "TradeFlow public v1 does not persist delivery fulfilment details yet"
            )
        data = self._shop_data(
            shop_id=request.shop_id,
            idempotency_key=idempotency_key,
            customer={
                "display_name": request.customer_name,
                "phone": request.contact_number,
            },
            items=[
                {
                    "business_product_id": request.business_product_id,
                    "quantity": request.quantity,
                }
            ],
        )
        result = await self._request("order.create", data, retryable=True)
        order = result.get("order")
        if not isinstance(order, dict):
            raise TradeFlowResponseError("TradeFlow order response is malformed")
        order_id = str(order.get("order_id") or order.get("id") or "").strip()
        status = str(order.get("status") or "requested").strip()
        if not order_id:
            raise TradeFlowResponseError("TradeFlow order response is missing order_id")
        return SubmissionResult(
            request_id=order_id,
            status=status,
            created=result.get("duplicate") is not True,
        )

    async def create_booking_request(
        self,
        business_id: str,
        request: BookingSubmissionRequest,
        *,
        idempotency_key: str,
    ) -> SubmissionResult:
        del request, idempotency_key
        self._assert_business(business_id)
        raise TradeFlowFeatureUnavailableError("Standard TradeFlow does not expose booking")

    async def search_business_products(
        self,
        business_id: str,
        query: str,
        *,
        limit: int = 12,
    ) -> tuple[BusinessProduct, ...]:
        """Search only this exact tenant's public local catalogue."""

        self._assert_business(business_id)
        data = await self._request("catalogue.search", self._shop_data(query=query))
        items = data.get("items") if isinstance(data.get("items"), list) else []
        return tuple(
            self._product(item, require_canonical=False)
            for item in items[: max(1, min(limit, 12))]
            if isinstance(item, dict)
        )

    def _shop_data(self, **values: Any) -> dict[str, Any]:
        data = {
            key: value
            for key, value in values.items()
            if value is not None and value != ""
        }
        if self.default_shop_id:
            data.setdefault("shop_id", self.default_shop_id)
        return data

    def _assert_business(self, business_id: str) -> None:
        if business_id.strip() != self.business_id:
            raise TradeFlowResponseError("TradeFlow tenant mismatch", code="TENANT_MISMATCH")

    async def _request(
        self,
        action: str,
        data: dict[str, Any],
        *,
        retryable: bool = True,
    ) -> dict[str, Any]:
        attempts = 2 if retryable else 1
        last_error: Exception | None = None
        for _attempt in range(attempts):
            envelope = self._envelope(action, data)
            try:
                response = await self._post(envelope)
            except (httpx.TimeoutException, httpx.NetworkError) as error:
                last_error = error
                continue
            try:
                payload = response.json()
            except ValueError as error:
                raise TradeFlowResponseError("TradeFlow returned a non-JSON response") from error
            if not isinstance(payload, dict):
                raise TradeFlowResponseError("TradeFlow response envelope is malformed")
            if response.status_code >= 500:
                last_error = TradeFlowUnavailableError("TradeFlow is temporarily unavailable")
                continue
            if payload.get("ok") is not True:
                details = payload.get("error") if isinstance(payload.get("error"), dict) else {}
                code = str(details.get("code") or "REQUEST_REJECTED")
                if code == "RATE_LIMITED" and retryable:
                    last_error = TradeFlowUnavailableError("TradeFlow is temporarily unavailable")
                    continue
                raise TradeFlowResponseError("TradeFlow rejected the request", code=code)
            result = payload.get("data")
            if not isinstance(result, dict):
                raise TradeFlowResponseError("TradeFlow response data is malformed")
            return result
        raise TradeFlowUnavailableError("TradeFlow is temporarily unavailable") from last_error

    async def _post(self, envelope: dict[str, Any]) -> httpx.Response:
        if self._client is not None:
            return await self._post_with_redirect_policy(
                self._client, envelope, validate_destinations=False
            )
        async with httpx.AsyncClient(
            timeout=self._timeout, verify=self._verify_tls, follow_redirects=False
        ) as client:
            return await self._post_with_redirect_policy(
                client, envelope, validate_destinations=True
            )

    async def _post_with_redirect_policy(
        self,
        client: httpx.AsyncClient,
        envelope: dict[str, Any],
        *,
        validate_destinations: bool,
    ) -> httpx.Response:
        """Follow a small, safe subset of public Apps Script redirects."""

        destination = self.base_url
        method = "POST"
        for _attempt in range(3):
            if validate_destinations:
                await self._assert_safe_destination(destination)
            response = await client.request(
                method,
                destination,
                json=envelope if method == "POST" else None,
                timeout=self._timeout,
            )
            if not response.is_redirect:
                return response
            if response.status_code not in {301, 302, 303}:
                raise TradeFlowResponseError(
                    "TradeFlow returned an unsafe redirect", code="UNSAFE_REDIRECT"
                )
            location = response.headers.get("location", "").strip()
            if not location:
                raise TradeFlowResponseError(
                    "TradeFlow returned an invalid redirect", code="INVALID_REDIRECT"
                )
            next_url = response.url.join(location)
            if next_url.scheme != "https" or next_url.username or next_url.password:
                raise TradeFlowResponseError(
                    "TradeFlow returned an unsafe redirect", code="UNSAFE_REDIRECT"
                )
            destination = str(next_url)
            # Do not forward the credential-bearing API envelope to a redirect
            # destination. Apps Script's 302 is completed as a credential-free GET.
            method = "GET"
        raise TradeFlowUnavailableError("TradeFlow redirect limit exceeded")

    async def _assert_safe_destination(self, destination: str | None = None) -> None:
        """Block DNS resolution to local, private, or metadata-address networks."""
        parsed = urlparse(destination or self.base_url)
        host = (parsed.hostname or "").strip().strip("[]").casefold()
        port = parsed.port or 443
        if not host:
            raise TradeFlowResponseError(
                "TradeFlow destination is invalid", code="UNSAFE_DESTINATION"
            )
        if host in self._allow_private_destination_hosts:
            return
        loop = asyncio.get_running_loop()
        try:
            records = await loop.getaddrinfo(
                host, port, type=socket.SOCK_STREAM
            )
        except OSError as error:
            raise TradeFlowUnavailableError("TradeFlow destination could not be resolved") from error
        addresses = {record[4][0] for record in records}
        if not addresses:
            raise TradeFlowUnavailableError("TradeFlow destination could not be resolved")
        for address_text in addresses:
            address = ip_address(address_text)
            if any((address.is_private, address.is_loopback, address.is_link_local,
                    address.is_multicast, address.is_reserved, address.is_unspecified)):
                raise TradeFlowResponseError(
                    "TradeFlow destination resolved to a non-public IP address",
                    code="UNSAFE_DESTINATION",
                )

    def _envelope(self, action: str, data: dict[str, Any]) -> dict[str, Any]:
        request_id = f"ntheemba-{uuid4().hex}"
        envelope: dict[str, Any] = {
            "version": "v1",
            "action": action,
            "request_id": request_id,
            "api_token": self._api_token,
            "business_id": self.business_id,
            "data": data,
        }
        if self._signing_secret is not None:
            timestamp = int(time.time() * 1000)
            nonce = secrets.token_urlsafe(18)
            envelope["request_timestamp"] = timestamp
            envelope["request_nonce"] = nonce
            envelope["request_signature"] = self._signature(
                request_id=request_id,
                action=action,
                timestamp=timestamp,
                nonce=nonce,
                data=data,
            )
        return envelope

    def _signature(
        self,
        *,
        request_id: str,
        action: str,
        timestamp: int,
        nonce: str,
        data: dict[str, Any],
    ) -> str:
        assert self._signing_secret is not None
        canonical_data = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        digest = hashlib.sha256(canonical_data.encode("utf-8")).hexdigest()
        material = "\n".join(
            [
                "v1",
                self.business_id,
                request_id,
                "",
                action,
                str(timestamp),
                nonce,
                digest,
            ]
        )
        signature = hmac.new(
            self._signing_secret.encode("utf-8"),
            material.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return base64.b64encode(signature).decode("ascii")

    @staticmethod
    def _product(
        item: dict[str, Any],
        *,
        require_canonical: bool = False,
    ) -> BusinessProduct:
        identity = item.get("identity") if isinstance(item.get("identity"), dict) else {}
        product_id = str(identity.get("ncpc_prd_id") or "").strip() or None
        variant_id = str(identity.get("ncpc_var_id") or "").strip() or None
        identity_status = str(
            item.get("identity_status")
            or identity.get("status")
            or ("linked" if product_id and variant_id else "local_only")
        ).strip().lower()
        if require_canonical and (not product_id or not variant_id):
            raise TradeFlowResponseError("TradeFlow canonical product identity is incomplete")
        try:
            price = Decimal(str(item.get("selling_price", 0)))
        except (InvalidOperation, ValueError) as error:
            raise TradeFlowResponseError("TradeFlow product price is malformed") from error
        availability = item.get("availability") if isinstance(item.get("availability"), dict) else {}
        return BusinessProduct(
            business_product_id=str(item.get("business_product_id") or ""),
            ncpc_product_id=product_id,
            ncpc_variant_id=variant_id,
            name=str(item.get("name") or ""),
            selling_price=price,
            currency=str(item.get("currency") or "ZMW"),
            available_quantity=1 if availability.get("status") == "in_stock" else 0,
            public_visible=True,
            barcode=str(item.get("barcode") or "").strip() or None,
            shop_id=str(item.get("shop_id") or ""),
            identity_status=identity_status,
            catalogue_source=str(item.get("catalogue_source") or "tradeflow_local_catalogue"),
        )


def _parse_clock(value: object) -> clock_time | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return clock_time.fromisoformat(text)
    except ValueError:
        return None
