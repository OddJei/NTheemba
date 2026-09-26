"""PostgreSQL persistence for platform-owned Marketplace state."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Any

from psycopg.types.json import Jsonb

from ntheemba.domain.marketplace import (
    MarketplaceBusinessListing,
    MarketplaceHandoff,
    MarketplaceHandoffStatus,
    MarketplaceListingStatus,
)


class PostgresMarketplaceRegistry:
    """Persist Marketplace participation and handoff snapshots outside business capabilities."""

    def __init__(self, pool: Any) -> None:
        self.pool = pool

    @asynccontextmanager
    async def _connection(self) -> AsyncIterator[Any]:
        async with self.pool.connection() as connection:
            async with connection.transaction():
                yield connection

    async def get_listing(self, business_id: str) -> MarketplaceBusinessListing | None:
        async with self._connection() as connection:
            cursor = await connection.execute(
                """
                SELECT business_id, status, discoverable, province_id, district_id,
                       town_id, area_text, metadata, updated_at
                  FROM marketplace_business_listings
                 WHERE business_id = %s
                """,
                (business_id,),
            )
            row = await cursor.fetchone()
        return None if row is None else self._listing(row)

    async def list_listings(self) -> tuple[MarketplaceBusinessListing, ...]:
        async with self._connection() as connection:
            cursor = await connection.execute(
                """
                SELECT business_id, status, discoverable, province_id, district_id,
                       town_id, area_text, metadata, updated_at
                  FROM marketplace_business_listings
                 ORDER BY business_id
                """
            )
            rows = await cursor.fetchall()
        return tuple(self._listing(row) for row in rows)

    async def save_listing(self, listing: MarketplaceBusinessListing) -> None:
        async with self._connection() as connection:
            await connection.execute(
                """
                INSERT INTO marketplace_business_listings (
                    business_id, status, discoverable, province_id, district_id,
                    town_id, area_text, metadata, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (business_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    discoverable = EXCLUDED.discoverable,
                    province_id = EXCLUDED.province_id,
                    district_id = EXCLUDED.district_id,
                    town_id = EXCLUDED.town_id,
                    area_text = EXCLUDED.area_text,
                    metadata = EXCLUDED.metadata,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    listing.business_id,
                    listing.status.value,
                    listing.discoverable,
                    listing.province_id,
                    listing.district_id,
                    listing.town_id,
                    listing.area_text,
                    Jsonb(dict(listing.metadata)),
                    listing.updated_at,
                ),
            )

    async def get_handoff(self, handoff_id: str) -> MarketplaceHandoff | None:
        async with self._connection() as connection:
            cursor = await connection.execute(
                """
                SELECT handoff_id, search_id, result_id, source_channel_id,
                       target_business_id, business_product_id, ncpc_product_id,
                       ncpc_variant_id, product_name, selling_price_snapshot,
                       currency, integration_id, business_runtime_revision,
                       shop_id, status, created_at, consumed_at
                  FROM marketplace_handoffs
                 WHERE handoff_id = %s
                """,
                (handoff_id,),
            )
            row = await cursor.fetchone()
        return None if row is None else self._handoff(row)

    async def get_handoff_for_result(
        self, search_id: str, result_id: str
    ) -> MarketplaceHandoff | None:
        async with self._connection() as connection:
            cursor = await connection.execute(
                """
                SELECT handoff_id, search_id, result_id, source_channel_id,
                       target_business_id, business_product_id, ncpc_product_id,
                       ncpc_variant_id, product_name, selling_price_snapshot,
                       currency, integration_id, business_runtime_revision,
                       shop_id, status, created_at, consumed_at
                  FROM marketplace_handoffs
                 WHERE search_id = %s AND result_id = %s
                """,
                (search_id, result_id),
            )
            row = await cursor.fetchone()
        return None if row is None else self._handoff(row)

    async def save_handoff(self, handoff: MarketplaceHandoff) -> None:
        async with self._connection() as connection:
            await connection.execute(
                """
                INSERT INTO marketplace_handoffs (
                    handoff_id, search_id, result_id, source_channel_id,
                    target_business_id, business_product_id, ncpc_product_id,
                    ncpc_variant_id, product_name, selling_price_snapshot,
                    currency, integration_id, business_runtime_revision,
                    shop_id, status, created_at, consumed_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (search_id, result_id) DO NOTHING
                """,
                (
                    handoff.handoff_id,
                    handoff.search_id,
                    handoff.result_id,
                    handoff.source_channel_id,
                    handoff.target_business_id,
                    handoff.business_product_id,
                    handoff.ncpc_product_id,
                    handoff.ncpc_variant_id,
                    handoff.product_name,
                    handoff.selling_price_snapshot,
                    handoff.currency,
                    handoff.integration_id,
                    handoff.business_runtime_revision,
                    handoff.shop_id,
                    handoff.status.value,
                    handoff.created_at,
                    handoff.consumed_at,
                ),
            )

    async def mark_handoff_consumed(
        self, handoff_id: str, *, consumed_at: datetime
    ) -> MarketplaceHandoff:
        async with self._connection() as connection:
            cursor = await connection.execute(
                """
                UPDATE marketplace_handoffs
                   SET status = 'consumed',
                       consumed_at = COALESCE(consumed_at, %s)
                 WHERE handoff_id = %s
                   AND status IN ('ready', 'consumed')
             RETURNING handoff_id, search_id, result_id, source_channel_id,
                       target_business_id, business_product_id, ncpc_product_id,
                       ncpc_variant_id, product_name, selling_price_snapshot,
                       currency, integration_id, business_runtime_revision,
                       shop_id, status, created_at, consumed_at
                """,
                (consumed_at, handoff_id),
            )
            row = await cursor.fetchone()
        if row is None:
            raise LookupError("Marketplace handoff cannot be consumed")
        return self._handoff(row)

    @staticmethod
    def _listing(row: Any) -> MarketplaceBusinessListing:
        return MarketplaceBusinessListing(
            business_id=str(row["business_id"]),
            status=MarketplaceListingStatus(str(row["status"])),
            discoverable=bool(row["discoverable"]),
            province_id=str(row.get("province_id") or ""),
            district_id=str(row.get("district_id") or ""),
            town_id=str(row.get("town_id") or ""),
            area_text=str(row.get("area_text") or ""),
            metadata=MappingProxyType(dict(row.get("metadata") or {})),
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _handoff(row: Any) -> MarketplaceHandoff:
        return MarketplaceHandoff(
            handoff_id=str(row["handoff_id"]),
            search_id=str(row["search_id"]),
            result_id=str(row["result_id"]),
            source_channel_id=str(row["source_channel_id"]),
            target_business_id=str(row["target_business_id"]),
            business_product_id=str(row["business_product_id"]),
            ncpc_product_id=str(row["ncpc_product_id"]),
            ncpc_variant_id=str(row["ncpc_variant_id"]),
            product_name=str(row["product_name"]),
            selling_price_snapshot=Decimal(str(row["selling_price_snapshot"])),
            currency=str(row["currency"]),
            integration_id=str(row["integration_id"]),
            business_runtime_revision=int(row["business_runtime_revision"]),
            shop_id=str(row.get("shop_id") or ""),
            status=MarketplaceHandoffStatus(str(row["status"])),
            created_at=row["created_at"],
            consumed_at=row.get("consumed_at"),
        )
