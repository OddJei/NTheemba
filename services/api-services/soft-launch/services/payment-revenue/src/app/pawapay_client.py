from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from src.app.config import get_http_timeout_seconds, get_pawapay_api_key, get_pawapay_base_url


@dataclass(frozen=True)
class PawaPayResponse:
    status_code: int
    body: dict[str, Any]


def _join_url(base: str, path: str) -> str:
    return f"{base.rstrip('/')}/{path.lstrip('/')}"


class PawaPayClient:
    def __init__(self) -> None:
        self._base_url = get_pawapay_base_url().rstrip("/")
        self._timeout = get_http_timeout_seconds()

        api_key = get_pawapay_api_key().strip()
        if not api_key:
            raise ValueError("pawapay_api_key_missing")
        self._api_key = api_key

    def _headers(self, *, correlation_id: str | None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if correlation_id:
            headers["X-Correlation-Id"] = correlation_id
        return headers

    async def post(self, *, path: str, json: dict[str, Any], correlation_id: str | None) -> PawaPayResponse:
        url = _join_url(self._base_url, path)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.post(url, json=json, headers=self._headers(correlation_id=correlation_id))

        try:
            body = r.json() if isinstance(r.json(), dict) else {"raw": r.text}
        except ValueError:
            body = {"raw": r.text}

        return PawaPayResponse(status_code=int(r.status_code), body=body)

    async def get(self, *, path: str, correlation_id: str | None) -> PawaPayResponse:
        url = _join_url(self._base_url, path)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.get(url, headers=self._headers(correlation_id=correlation_id))

        try:
            body = r.json() if isinstance(r.json(), dict) else {"raw": r.text}
        except ValueError:
            body = {"raw": r.text}

        return PawaPayResponse(status_code=int(r.status_code), body=body)


async def initiate_deposit(*, deposit_id: str, amount: str, currency: str, phone_number: str, provider: str, correlation_id: str | None) -> PawaPayResponse:
    payload = {
        "depositId": deposit_id,
        "amount": amount,
        "currency": currency,
        "payer": {
            "type": "MMO",
            "accountDetails": {"phoneNumber": phone_number, "provider": provider},
        },
    }
    return await PawaPayClient().post(path="/deposits", json=payload, correlation_id=correlation_id)


async def initiate_payout(*, payout_id: str, amount: str, currency: str, phone_number: str, provider: str, correlation_id: str | None) -> PawaPayResponse:
    payload = {
        "payoutId": payout_id,
        "amount": amount,
        "currency": currency,
        "recipient": {
            "type": "MMO",
            "accountDetails": {"phoneNumber": phone_number, "provider": provider},
        },
    }
    return await PawaPayClient().post(path="/payouts", json=payload, correlation_id=correlation_id)


async def initiate_refund(*, refund_id: str, deposit_id: str, amount: str | None, currency: str | None, correlation_id: str | None) -> PawaPayResponse:
    payload: dict[str, Any] = {"refundId": refund_id, "depositId": deposit_id}
    if amount is not None:
        payload["amount"] = amount
    if currency is not None:
        payload["currency"] = currency
    return await PawaPayClient().post(path="/refunds", json=payload, correlation_id=correlation_id)


async def get_deposit_status(*, deposit_id: str, correlation_id: str | None) -> PawaPayResponse:
    return await PawaPayClient().get(path=f"/deposits/{deposit_id}", correlation_id=correlation_id)


async def get_payout_status(*, payout_id: str, correlation_id: str | None) -> PawaPayResponse:
    return await PawaPayClient().get(path=f"/payouts/{payout_id}", correlation_id=correlation_id)


async def get_refund_status(*, refund_id: str, correlation_id: str | None) -> PawaPayResponse:
    return await PawaPayClient().get(path=f"/refunds/{refund_id}", correlation_id=correlation_id)
