"""PostgreSQL business/channel registry and unknown-declaration observations."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import MappingProxyType
from typing import Any

from psycopg.types.json import Jsonb

from ntheemba.domain.business import (
    BusinessShop, ChannelBinding, ChannelRole, ChannelScope, BusinessChannel, BusinessIntegration, BusinessProfile,
)
from ntheemba.ports.businesses import (
    UnsupportedDeclarationKind,
    UnsupportedDeclarationObservation,
)


class PostgresBusinessRegistry:
    def __init__(self, pool: Any) -> None:
        self.pool = pool

    @asynccontextmanager
    async def _connection(self) -> AsyncIterator[Any]:
        async with self.pool.connection() as connection:
            async with connection.transaction():
                yield connection

    async def get_business(self, business_id: str) -> BusinessProfile | None:
        async with self._connection() as connection:
            cursor = await connection.execute(
                """
                SELECT business_id, display_name, adapter_type, enabled,
                       business_type, description, runtime_revision
                  FROM businesses WHERE business_id = %s
                """,
                (business_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            capabilities, capability_config = await self._capabilities(connection, business_id)
        return self._business(row, capabilities, capability_config)

    async def get_channel(self, channel_instance_id: str) -> ChannelBinding | None:
        async with self._connection() as connection:
            cursor = await connection.execute(
                """
                SELECT channel_instance_id, provider, business_id, phone_e164, enabled,
                       scope, role, is_primary, external_session_id, recipient_identifier
                  FROM business_channels WHERE channel_instance_id = %s
                """,
                (channel_instance_id,),
            )
            row = await cursor.fetchone()
        return None if row is None else self._channel(row)

    async def get_channel_by_identity(
        self, provider: str, external_session_id: str, recipient_identifier: str
    ) -> ChannelBinding | None:
        async with self._connection() as connection:
            cursor = await connection.execute(
                """
                SELECT channel_instance_id, provider, business_id, phone_e164, enabled,
                       scope, role, is_primary, external_session_id, recipient_identifier
                  FROM business_channels
                 WHERE provider = %s
                   AND external_session_id = %s
                   AND recipient_identifier = %s
                """,
                (provider, external_session_id, recipient_identifier),
            )
            row = await cursor.fetchone()
        return None if row is None else self._channel(row)

    async def list_businesses(self) -> tuple[BusinessProfile, ...]:
        async with self._connection() as connection:
            cursor = await connection.execute(
                """
                SELECT business_id, display_name, adapter_type, enabled,
                       business_type, description, runtime_revision
                  FROM businesses ORDER BY business_id
                """
            )
            rows = await cursor.fetchall()
            result = []
            for row in rows:
                business_id = str(row["business_id"])
                capabilities, capability_config = await self._capabilities(connection, business_id)
                result.append(self._business(row, capabilities, capability_config))
        return tuple(result)

    async def list_channels(self) -> tuple[BusinessChannel, ...]:
        async with self._connection() as connection:
            cursor = await connection.execute(
                """
                SELECT channel_instance_id, provider, business_id, phone_e164, enabled,
                       scope, role, is_primary, external_session_id, recipient_identifier
                  FROM business_channels ORDER BY channel_instance_id
                """
            )
            rows = await cursor.fetchall()
        return tuple(self._channel(row) for row in rows)

    async def list_integrations(self, business_id: str) -> tuple[BusinessIntegration, ...]:
        async with self._connection() as connection:
            cursor = await connection.execute(
                """
                SELECT integration_id, business_id, provider, adapter_type, base_url,
                       api_version, auth_reference, status, enabled, capabilities, config
                  FROM business_integrations
                 WHERE business_id = %s
                 ORDER BY integration_id
                """,
                (business_id,),
            )
            rows = await cursor.fetchall()
        return tuple(self._integration(row) for row in rows)

    async def list_shops(self, business_id: str) -> tuple[BusinessShop, ...]:
        async with self._connection() as connection:
            cursor = await connection.execute(
                """SELECT business_id, shop_id, display_name, status, is_primary,
                          location, hours_status, source_revision
                     FROM business_shops WHERE business_id = %s ORDER BY shop_id""",
                (business_id,),
            )
            rows = await cursor.fetchall()
        return tuple(self._shop(row) for row in rows)

    async def register_business(self, business: BusinessProfile) -> None:
        async with self._connection() as connection:
            await connection.execute(
                """
                INSERT INTO businesses (
                    business_id, display_name, adapter_type, business_type,
                    description, enabled, runtime_revision, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (business_id) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    adapter_type = EXCLUDED.adapter_type,
                    business_type = EXCLUDED.business_type,
                    description = EXCLUDED.description,
                    enabled = EXCLUDED.enabled,
                    updated_at = NOW()
                """,
                (
                    business.business_id,
                    business.display_name,
                    business.adapter_type,
                    business.business_type,
                    business.description,
                    business.enabled,
                    business.runtime_revision,
                ),
            )
            await connection.execute(
                "DELETE FROM business_capabilities WHERE business_id = %s",
                (business.business_id,),
            )
            for capability in sorted(business.declared_capabilities):
                await connection.execute(
                    """
                    INSERT INTO business_capabilities (
                        business_id, capability_id, enabled, config
                    ) VALUES (%s, %s, TRUE, %s::jsonb)
                    """,
                    (
                        business.business_id,
                        capability,
                        Jsonb(dict(business.capability_config.get(capability, {}))),
                    ),
                )
            await connection.execute(
                """
                UPDATE businesses
                   SET runtime_revision = runtime_revision + 1,
                       updated_at = NOW()
                 WHERE business_id = %s
                """,
                (business.business_id,),
            )

    async def register_channel(self, channel: ChannelBinding) -> None:
        async with self._connection() as connection:
            existing_cursor = await connection.execute(
                "SELECT business_id, scope FROM business_channels "
                "WHERE channel_instance_id = %s FOR UPDATE",
                (channel.channel_instance_id,),
            )
            existing = await existing_cursor.fetchone()
            if existing is not None:
                existing_business = (
                    None if existing["business_id"] is None else str(existing["business_id"])
                )
                if existing_business != channel.business_id or str(existing["scope"]) != channel.scope.value:
                    raise ValueError(
                        f"channel {channel.channel_instance_id!r} ownership is immutable"
                    )
            identity_cursor = await connection.execute(
                """
                SELECT channel_instance_id
                  FROM business_channels
                 WHERE provider = %s
                   AND external_session_id = %s
                   AND recipient_identifier = %s
                   AND channel_instance_id <> %s
                 FOR UPDATE
                """,
                (*channel.exact_identity, channel.channel_instance_id),
            )
            if await identity_cursor.fetchone() is not None:
                raise ValueError("external channel identity is already registered")

            if channel.is_primary:
                if channel.scope is ChannelScope.BUSINESS:
                    await connection.execute(
                        """
                        UPDATE business_channels
                           SET is_primary = FALSE, updated_at = NOW()
                         WHERE scope = 'business'
                           AND business_id = %s
                           AND role = %s
                           AND channel_instance_id <> %s
                        """,
                        (channel.business_id, channel.role.value, channel.channel_instance_id),
                    )
                else:
                    await connection.execute(
                        """
                        UPDATE business_channels
                           SET is_primary = FALSE, updated_at = NOW()
                         WHERE scope = 'platform'
                           AND role = %s
                           AND channel_instance_id <> %s
                        """,
                        (channel.role.value, channel.channel_instance_id),
                    )

            await connection.execute(
                """
                INSERT INTO business_channels (
                    channel_instance_id, provider, business_id, phone_e164, enabled,
                    scope, role, is_primary, external_session_id, recipient_identifier, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (channel_instance_id) DO UPDATE SET
                    provider = EXCLUDED.provider,
                    phone_e164 = EXCLUDED.phone_e164,
                    enabled = EXCLUDED.enabled,
                    role = EXCLUDED.role,
                    is_primary = EXCLUDED.is_primary,
                    external_session_id = EXCLUDED.external_session_id,
                    recipient_identifier = EXCLUDED.recipient_identifier,
                    updated_at = NOW()
                """,
                (
                    channel.channel_instance_id,
                    channel.provider,
                    channel.business_id,
                    channel.phone_e164,
                    channel.enabled,
                    channel.scope.value,
                    channel.role.value,
                    channel.is_primary,
                    channel.external_session_id,
                    channel.recipient_identifier,
                ),
            )
            if channel.business_id is not None:
                await connection.execute(
                    """
                    UPDATE businesses
                       SET runtime_revision = runtime_revision + 1,
                           updated_at = NOW()
                     WHERE business_id = %s
                    """,
                    (channel.business_id,),
                )

    async def register_integration(self, integration: BusinessIntegration) -> None:
        async with self._connection() as connection:
            existing_cursor = await connection.execute(
                "SELECT business_id FROM business_integrations "
                "WHERE integration_id = %s FOR UPDATE",
                (integration.integration_id,),
            )
            existing = await existing_cursor.fetchone()
            if existing is not None and str(existing["business_id"]) != integration.business_id:
                raise ValueError(
                    f"integration {integration.integration_id!r} belongs to another business"
                )
            await connection.execute(
                """
                INSERT INTO business_integrations (
                    integration_id, business_id, provider, adapter_type, base_url,
                    api_version, auth_reference, status, enabled, capabilities, config, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
                ON CONFLICT (integration_id) DO UPDATE SET
                    provider = EXCLUDED.provider,
                    adapter_type = EXCLUDED.adapter_type,
                    base_url = EXCLUDED.base_url,
                    api_version = EXCLUDED.api_version,
                    auth_reference = EXCLUDED.auth_reference,
                    status = EXCLUDED.status,
                    enabled = EXCLUDED.enabled,
                    capabilities = EXCLUDED.capabilities,
                    config = EXCLUDED.config,
                    updated_at = NOW()
                """,
                (
                    integration.integration_id,
                    integration.business_id,
                    integration.provider,
                    integration.adapter_type,
                    integration.base_url,
                    integration.api_version,
                    integration.auth_reference,
                    integration.status,
                    integration.enabled,
                    sorted(integration.capabilities),
                    Jsonb(dict(integration.config)),
                ),
            )
            await connection.execute(
                """
                UPDATE businesses
                   SET runtime_revision = runtime_revision + 1,
                       updated_at = NOW()
                 WHERE business_id = %s
                """,
                (integration.business_id,),
            )

    async def register_shop(self, shop: BusinessShop) -> None:
        async with self._connection() as connection:
            if shop.is_primary:
                await connection.execute(
                    "UPDATE business_shops SET is_primary = FALSE, updated_at = NOW() "
                    "WHERE business_id = %s AND shop_id <> %s",
                    (shop.business_id, shop.shop_id),
                )
            await connection.execute(
                """INSERT INTO business_shops (
                       business_id, shop_id, display_name, status, is_primary,
                       location, hours_status, source_revision, updated_at
                   ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, NOW())
                   ON CONFLICT (business_id, shop_id) DO UPDATE SET
                       display_name = EXCLUDED.display_name, status = EXCLUDED.status,
                       is_primary = EXCLUDED.is_primary, location = EXCLUDED.location,
                       hours_status = EXCLUDED.hours_status,
                       source_revision = EXCLUDED.source_revision, updated_at = NOW()""",
                (shop.business_id, shop.shop_id, shop.display_name, shop.status, shop.is_primary,
                 Jsonb(dict(shop.location)), shop.hours_status, shop.source_revision),
            )
            await connection.execute(
                "UPDATE businesses SET runtime_revision = runtime_revision + 1, updated_at = NOW() WHERE business_id = %s",
                (shop.business_id,),
            )

    async def _capabilities(
        self,
        connection: Any,
        business_id: str,
    ) -> tuple[frozenset[str], MappingProxyType[str, MappingProxyType[str, Any]]]:
        cursor = await connection.execute(
            """
            SELECT capability_id, config
              FROM business_capabilities
             WHERE business_id = %s
               AND enabled = TRUE
             ORDER BY capability_id
            """,
            (business_id,),
        )
        rows = await cursor.fetchall()
        configs = {
            str(row["capability_id"]): MappingProxyType(dict(row["config"] or {}))
            for row in rows
        }
        return frozenset(configs), MappingProxyType(configs)

    @staticmethod
    def _business(
        row: Any,
        capabilities: frozenset[str],
        capability_config: MappingProxyType[str, MappingProxyType[str, Any]],
    ) -> BusinessProfile:
        return BusinessProfile(
            business_id=str(row["business_id"]),
            display_name=str(row["display_name"]),
            adapter_type=str(row["adapter_type"]),
            declared_capabilities=capabilities,
            enabled=bool(row["enabled"]),
            business_type=str(row["business_type"] or ""),
            description=str(row["description"] or ""),
            runtime_revision=int(row["runtime_revision"] or 0),
            capability_config=capability_config,
        )

    @staticmethod
    def _channel(row: Any) -> ChannelBinding:
        raw_business_id = row["business_id"]
        return ChannelBinding(
            channel_instance_id=str(row["channel_instance_id"]),
            provider=str(row["provider"]),
            business_id=None if raw_business_id is None else str(raw_business_id),
            phone_e164=str(row["phone_e164"]),
            enabled=bool(row["enabled"]),
            scope=ChannelScope(str(row.get("scope", "business"))),
            role=ChannelRole(str(row.get("role", "business_primary"))),
            is_primary=bool(row.get("is_primary", False)),
            external_session_id=str(row.get("external_session_id") or row["channel_instance_id"]),
            recipient_identifier=str(row.get("recipient_identifier") or row["phone_e164"]),
        )

    @staticmethod
    def _integration(row: Any) -> BusinessIntegration:
        raw_config = row["config"] or {}
        return BusinessIntegration(
            integration_id=str(row["integration_id"]),
            business_id=str(row["business_id"]),
            provider=str(row["provider"] or "google_apps_script"),
            adapter_type=str(row["adapter_type"]),
            base_url=str(row["base_url"]),
            api_version=str(row["api_version"] or "tradeflow.ntheemba.v1"),
            auth_reference=str(row["auth_reference"] or ""),
            status=str(row["status"] or "active"),
            enabled=bool(row["enabled"]),
            capabilities=frozenset(str(item) for item in (row["capabilities"] or [])),
            config=MappingProxyType(dict(raw_config)),
        )

    @staticmethod
    def _shop(row: Any) -> BusinessShop:
        return BusinessShop(
            business_id=str(row["business_id"]), shop_id=str(row["shop_id"]),
            display_name=str(row["display_name"]), status=str(row["status"]),
            is_primary=bool(row["is_primary"]), location=MappingProxyType(dict(row["location"] or {})),
            hours_status=str(row["hours_status"]), source_revision=str(row["source_revision"] or ""),
        )


class PostgresUnsupportedDeclarationSink:
    def __init__(self, pool: Any) -> None:
        self.pool = pool

    async def record(self, observation: UnsupportedDeclarationObservation) -> None:
        async with self.pool.connection() as connection:
            async with connection.transaction():
                await connection.execute(
                    """
                    INSERT INTO unsupported_declarations (
                        kind, value, business_id, adapter_type, source,
                        first_observed_at, last_observed_at, observation_count
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, 1)
                    ON CONFLICT (kind, value, business_id, adapter_type, source) DO UPDATE SET
                        last_observed_at = EXCLUDED.last_observed_at,
                        observation_count = unsupported_declarations.observation_count + 1
                    """,
                    (
                        observation.kind.value,
                        observation.value,
                        observation.business_id,
                        observation.adapter_type,
                        observation.source,
                        observation.observed_at,
                        observation.observed_at,
                    ),
                )

    async def list_observations(self) -> tuple[UnsupportedDeclarationObservation, ...]:
        async with self.pool.connection() as connection:
            cursor = await connection.execute(
                """
                SELECT kind, value, business_id, adapter_type, source, last_observed_at
                  FROM unsupported_declarations
                 ORDER BY last_observed_at DESC
                """
            )
            rows = await cursor.fetchall()
        return tuple(
            UnsupportedDeclarationObservation(
                kind=UnsupportedDeclarationKind(str(row["kind"])),
                value=str(row["value"]),
                business_id=str(row["business_id"]),
                adapter_type=str(row["adapter_type"]),
                source=str(row["source"]),
                observed_at=row["last_observed_at"],
            )
            for row in rows
        )
