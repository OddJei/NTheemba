from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("psycopg")

from ntheemba.domain.business import BusinessChannel, BusinessIntegration, BusinessProfile
from ntheemba.domain.capabilities import Capability
from ntheemba.infrastructure.postgres.businesses import PostgresBusinessRegistry
from psycopg.types.json import Jsonb


class _Cursor:
    async def fetchone(self) -> None:
        return None

    async def fetchall(self) -> list[Any]:
        return []


class _Connection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def transaction(self) -> _Transaction:
        return _Transaction()

    async def execute(self, sql: str, params: tuple[Any, ...] = ()) -> _Cursor:
        self.calls.append((sql, params))
        return _Cursor()


class _Transaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *args: object) -> None:
        return None


class _ConnectionContext:
    def __init__(self, connection: _Connection) -> None:
        self.connection = connection

    async def __aenter__(self) -> _Connection:
        return self.connection

    async def __aexit__(self, *args: object) -> None:
        return None


class _Pool:
    def __init__(self, connection: _Connection) -> None:
        self._connection = connection

    def connection(self) -> _ConnectionContext:
        return _ConnectionContext(self._connection)


@pytest.mark.asyncio
async def test_register_integration_adapts_config_as_jsonb_and_bumps_revision() -> None:
    connection = _Connection()
    registry = PostgresBusinessRegistry(_Pool(connection))

    await registry.register_integration(
        BusinessIntegration(
            integration_id="serah-tradeflow",
            business_id="serah",
            adapter_type="tradeflow_serahs",
            base_url="https://tradeflow.local/serah",
            capabilities=frozenset({Capability.APPOINTMENT_CREATE.value}),
            config={"contract": "tradeflow.ntheemba.v1"},
        )
    )

    insert_params = connection.calls[1][1]
    assert insert_params[4] == "https://tradeflow.local/serah"
    assert insert_params[5] == "tradeflow.ntheemba.v1"
    assert insert_params[6] == ""
    assert insert_params[7] == "active"
    assert insert_params[9] == [Capability.APPOINTMENT_CREATE.value]
    assert isinstance(insert_params[10], Jsonb)
    assert "runtime_revision = runtime_revision + 1" in connection.calls[2][0]
    assert connection.calls[2][1] == ("serah",)


@pytest.mark.asyncio
async def test_register_business_replaces_capabilities_and_bumps_revision_once() -> None:
    connection = _Connection()
    registry = PostgresBusinessRegistry(_Pool(connection))

    await registry.register_business(
        BusinessProfile(
            business_id="serah",
            display_name="Serah's Glow",
            adapter_type="tradeflow_serahs",
            declared_capabilities=frozenset({Capability.SERVICE_CATALOGUE.value}),
            runtime_revision=3,
            capability_config={
                Capability.SERVICE_CATALOGUE.value: {"visible": True},
            },
        )
    )

    assert "runtime_revision = businesses.runtime_revision + 1" not in connection.calls[0][0]
    assert "DELETE FROM business_capabilities" in connection.calls[1][0]
    assert isinstance(connection.calls[2][1][2], Jsonb)
    assert "runtime_revision = runtime_revision + 1" in connection.calls[3][0]
    assert connection.calls[3][1] == ("serah",)


@pytest.mark.asyncio
async def test_register_channel_bumps_business_revision() -> None:
    connection = _Connection()
    registry = PostgresBusinessRegistry(_Pool(connection))

    await registry.register_channel(
        BusinessChannel("wa-serah", "openwa", "serah", "+260970000002")
    )

    # Ownership and canonical-identity locks must run before the upsert.  This
    # preserves the N22 direct-persistence guard against cross-business channel
    # reassignment rather than merely asserting the old insert-first sequence.
    assert "SELECT business_id, scope FROM business_channels" in connection.calls[0][0]
    assert "SELECT channel_instance_id" in connection.calls[1][0]
    assert "INSERT INTO business_channels" in connection.calls[2][0]
    assert "runtime_revision = runtime_revision + 1" in connection.calls[3][0]
    assert connection.calls[3][1] == ("serah",)
