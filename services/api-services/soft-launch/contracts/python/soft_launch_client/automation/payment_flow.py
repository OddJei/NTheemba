from __future__ import annotations

from typing import Any, Dict, Optional

from ..adapters.payment import PaymentRevenueAdapter


class PaymentFlowPlugin:
    """Automation plugin: initiate + verify payment.

    Reference scaffold; align with your gateway (PawaPay sandbox) callbacks/verification.
    """

    def __init__(self, *, payment: PaymentRevenueAdapter) -> None:
        self._payment = payment

    async def handle(
        self,
        *,
        business_id: str,
        order_id: Optional[str],
        user_phone: Optional[str],
        amount: float,
        currency: str,
        correlation_id: str,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        init_resp = await self._payment.initiate_payment(
            business_id=business_id,
            order_id=order_id,
            user_phone=user_phone,
            amount=amount,
            currency=currency,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

        init_body = init_resp.body or {}
        payment_id = init_body.get("payment_id") or init_body.get("id")

        verify_resp = await self._payment.verify_payment(
            payment_id=str(payment_id),
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

        return {"payment_initiated": init_body, "payment_verified": verify_resp.body}
