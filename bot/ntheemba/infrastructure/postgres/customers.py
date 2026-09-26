"""PostgreSQL minimal platform-customer and business-client directory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, AsyncIterator
from uuid import uuid4

from ntheemba.domain.customers import (
    BusinessClientLink,
    PlatformCustomer,
    normalize_phone_e164,
)


class PostgresCustomerDirectory:
    def __init__(self, pool: Any, *, default_country_code: str = "+260") -> None:
        self.pool = pool
        self.default_country_code = default_country_code.lstrip("+")

    @asynccontextmanager
    async def _connection(self) -> AsyncIterator[Any]:
        async with self.pool.connection() as connection:
            async with connection.transaction():
                yield connection

    @asynccontextmanager
    async def _tenant_connection(
        self,
        business_id: str,
        customer_id: str,
    ) -> AsyncIterator[Any]:
        async with self._connection() as connection:
            await connection.execute(
                "SELECT set_config('app.business_id', %s, TRUE)", (business_id,)
            )
            await connection.execute(
                "SELECT set_config('app.customer_id', %s, TRUE)", (customer_id,)
            )
            yield connection

    async def resolve_by_phone(self, phone_e164: str) -> PlatformCustomer:
        phone = normalize_phone_e164(
            phone_e164,
            default_country_code=self.default_country_code,
        )
        now = datetime.now(UTC)
        candidate_id = f"CUST-{uuid4()}"
        async with self._connection() as connection:
            cursor = await connection.execute(
                """
                INSERT INTO customers (
                    customer_id, phone_e164, preferred_name, preferred_language,
                    created_at, last_seen_at, status
                ) VALUES (%s, %s, '', 'en', %s, %s, 'active')
                ON CONFLICT (phone_e164) DO UPDATE SET
                    last_seen_at = EXCLUDED.last_seen_at
                RETURNING customer_id, phone_e164, preferred_name,
                          preferred_language, created_at, last_seen_at
                """,
                (candidate_id, phone, now, now),
            )
            row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("PostgreSQL did not return the customer")
        return self._customer(row)

    async def get_customer(self, customer_id: str) -> PlatformCustomer | None:
        async with self._connection() as connection:
            cursor = await connection.execute(
                """
                SELECT customer_id, phone_e164, preferred_name,
                       preferred_language, created_at, last_seen_at
                  FROM customers
                 WHERE customer_id = %s AND status = 'active'
                """,
                (customer_id,),
            )
            row = await cursor.fetchone()
        return None if row is None else self._customer(row)

    async def update_preferred_name(
        self,
        customer_id: str,
        preferred_name: str,
    ) -> PlatformCustomer:
        name = preferred_name.strip()
        if len(name) < 2:
            raise ValueError("preferred_name is invalid")
        now = datetime.now(UTC)
        async with self._connection() as connection:
            cursor = await connection.execute(
                """
                UPDATE customers
                   SET preferred_name = %s, last_seen_at = %s
                 WHERE customer_id = %s AND status = 'active'
                RETURNING customer_id, phone_e164, preferred_name,
                          preferred_language, created_at, last_seen_at
                """,
                (name, now, customer_id),
            )
            row = await cursor.fetchone()
        if row is None:
            raise LookupError(customer_id)
        return self._customer(row)

    async def get_business_link(
        self,
        business_id: str,
        customer_id: str,
    ) -> BusinessClientLink | None:
        async with self._tenant_connection(business_id, customer_id) as connection:
            cursor = await connection.execute(
                """
                SELECT business_id, customer_id, external_client_id,
                       business_display_name, first_seen_at, last_seen_at
                  FROM business_clients
                 WHERE business_id = %s AND customer_id = %s
                """,
                (business_id, customer_id),
            )
            row = await cursor.fetchone()
        return None if row is None else self._link(row)

    async def save_business_link(self, link: BusinessClientLink) -> BusinessClientLink:
        async with self._tenant_connection(link.business_id, link.customer_id) as connection:
            cursor = await connection.execute(
                """
                INSERT INTO business_clients (
                    business_id, customer_id, external_client_id,
                    business_display_name, first_seen_at, last_seen_at
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (business_id, customer_id) DO UPDATE SET
                    external_client_id = EXCLUDED.external_client_id,
                    business_display_name = EXCLUDED.business_display_name,
                    last_seen_at = EXCLUDED.last_seen_at
                RETURNING business_id, customer_id, external_client_id,
                          business_display_name, first_seen_at, last_seen_at
                """,
                (
                    link.business_id,
                    link.customer_id,
                    link.external_client_id,
                    link.business_display_name,
                    link.first_seen_at,
                    link.last_seen_at,
                ),
            )
            row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("PostgreSQL did not return the business-client link")
        return self._link(row)

    @staticmethod
    def _customer(row: Any) -> PlatformCustomer:
        return PlatformCustomer(
            customer_id=str(row["customer_id"]),
            phone_e164=str(row["phone_e164"]),
            preferred_name=str(row["preferred_name"] or ""),
            preferred_language=str(row["preferred_language"] or "en"),
            created_at=row["created_at"],
            last_seen_at=row["last_seen_at"],
        )

    @staticmethod
    def _link(row: Any) -> BusinessClientLink:
        return BusinessClientLink(
            business_id=str(row["business_id"]),
            customer_id=str(row["customer_id"]),
            external_client_id=str(row["external_client_id"]),
            business_display_name=str(row["business_display_name"] or ""),
            first_seen_at=row["first_seen_at"],
            last_seen_at=row["last_seen_at"],
        )
