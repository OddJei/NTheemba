"""Phase 12 runtime composition for Redis and PostgreSQL durability."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from ntheemba.adapters.businesses import (
    InMemoryBusinessRegistry,
    InMemoryUnsupportedDeclarationSink,
)
from ntheemba.adapters.businesses.seeds import (
    reference_businesses,
    reference_channels,
    reference_integrations,
)
from ntheemba.adapters.customers import InMemoryCustomerDirectory
from ntheemba.adapters.gateway.in_memory import InMemoryReliableGatewayQueue
from ntheemba.adapters.marketplace import InMemoryMarketplaceRegistry
from ntheemba.application.customer_memory import CustomerMemoryService
from ntheemba.application.session_coordinator import SessionCoordinator
from ntheemba.config import Settings
from ntheemba.infrastructure.memory import (
    MemoryAuditSink,
    MemoryCustomerMemoryRepository,
    MemoryDeduplicationStore,
    MemoryIdempotencyStore,
    MemoryPlatformSessionLockManager,
    MemoryPlatformSessionRepository,
    MemorySessionLockManager,
    MemorySessionRepository,
)
from ntheemba.ports.businesses import (
    BusinessRegistry,
    RuntimeProfileCache,
    UnsupportedDeclarationSink,
)
from ntheemba.ports.customer_memory import CustomerMemoryRepository
from ntheemba.ports.customers import CustomerDirectory
from ntheemba.ports.gateway import ReliableGatewayQueue
from ntheemba.ports.idempotency import IdempotencyStore
from ntheemba.ports.marketplace import MutableMarketplaceRegistry
from ntheemba.ports.platform_sessions import PlatformSessionLockManager, PlatformSessionRepository
from ntheemba.ports.sessions import DeduplicationStore, SessionLockManager, SessionRepository


@dataclass(frozen=True, slots=True)
class StorageSnapshot:
    opened: bool
    session_backend: str
    customer_backend: str
    business_backend: str
    gateway_queue_backend: str
    redis_ready: bool
    postgres_ready: bool
    detail: str


class StorageRuntime:
    """Own configured storage clients and all durable ports."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.redis_runtime: Any | None = None
        self.postgres_runtime: Any | None = None

        self.session_repository: SessionRepository = MemorySessionRepository()
        self.session_locks: SessionLockManager = MemorySessionLockManager()
        self.platform_session_repository: PlatformSessionRepository = (
            MemoryPlatformSessionRepository()
        )
        self.platform_session_locks: PlatformSessionLockManager = (
            MemoryPlatformSessionLockManager()
        )
        self.deduplication: DeduplicationStore = MemoryDeduplicationStore()
        self.idempotency: IdempotencyStore = MemoryIdempotencyStore()
        self.customer_directory: CustomerDirectory = InMemoryCustomerDirectory()
        self.customer_memory_repository: CustomerMemoryRepository = (
            MemoryCustomerMemoryRepository()
        )
        self.audit_sink: Any = MemoryAuditSink()
        self.business_registry: BusinessRegistry = InMemoryBusinessRegistry(
            businesses=reference_businesses(),
            channels=reference_channels(),
            integrations=reference_integrations(),
        )
        self.unsupported_declarations: UnsupportedDeclarationSink = (
            InMemoryUnsupportedDeclarationSink()
        )
        self.marketplace_registry: MutableMarketplaceRegistry = InMemoryMarketplaceRegistry()
        from ntheemba.adapters.businesses import InMemoryRuntimeProfileCache

        self.runtime_profile_cache: RuntimeProfileCache = InMemoryRuntimeProfileCache()
        self.gateway_queue: ReliableGatewayQueue = InMemoryReliableGatewayQueue()
        self.opened = False

    @property
    def session_coordinator(self) -> SessionCoordinator:
        return SessionCoordinator(
            self.session_repository,
            self.session_locks,
            ttl=timedelta(seconds=self.settings.session_ttl_seconds),
            lock_timeout=self.settings.lock_acquire_timeout_seconds,
        )

    @property
    def customer_memory(self) -> CustomerMemoryService:
        return CustomerMemoryService(self.customer_memory_repository)

    def build_session_coordinator(self) -> SessionCoordinator:
        """Compatibility helper returning a coordinator over the configured adapters."""

        return self.session_coordinator

    def build_platform_session_coordinator(self) -> Any:
        """Build provider-neutral platform session coordination over configured storage."""

        from ntheemba.application.platform_session_coordinator import PlatformSessionCoordinator

        return PlatformSessionCoordinator(
            self.platform_session_repository,
            self.platform_session_locks,
            ttl=timedelta(seconds=self.settings.session_ttl_seconds),
            lock_timeout=self.settings.lock_acquire_timeout_seconds,
        )

    def build_customer_bridge(self, clients: Any) -> Any:
        """Build the minimal customer/client bridge with consent enforcement."""

        from ntheemba.application.customer_bridge import CustomerBridgeService

        return CustomerBridgeService(
            customers=self.customer_directory,
            clients=clients,
            consents=self.customer_memory,
        )

    def build_business_context_resolver(self, *, tracer: Any | None = None) -> Any:
        """Build channel routing over Ntheemba's closed capability catalogue."""

        from ntheemba.application.capability_runtime import BusinessContextResolver
        from ntheemba.application.runtime_profiles import RuntimeProfileCompiler
        from ntheemba.domain.capabilities import CapabilityCatalogue

        catalogue = CapabilityCatalogue.canonical()
        return BusinessContextResolver(
            registry=self.business_registry,
            catalogue=catalogue,
            observations=self.unsupported_declarations,
            profile_compiler=RuntimeProfileCompiler(
                registry=self.business_registry,
                catalogue=catalogue,
                cache=self.runtime_profile_cache,
            ),
            tracer=tracer,
        )

    def build_channel_context_resolver(self, *, tracer: Any | None = None) -> Any:
        """Resolve exact external identities to BUSINESS or PLATFORM context."""

        from ntheemba.application.capability_runtime import ChannelContextResolver

        business = self.build_business_context_resolver(tracer=tracer)
        return ChannelContextResolver(
            registry=self.business_registry,
            business_resolver=business,
        )

    def build_gateway_publisher(self) -> Any:
        """Build exact-channel durable reply publication."""

        from ntheemba.adapters.gateway.publisher import ReliableGatewayPublisher

        return ReliableGatewayPublisher(
            self.gateway_queue,
            self.idempotency,
            self.business_registry,
            ttl=timedelta(seconds=self.settings.idempotency_ttl_seconds),
            transport_gateway_ids=frozenset(self.settings.transport_gateway_tokens),
        )

    async def open(self) -> None:
        if self.opened:
            return
        try:
            if self._redis_required:
                await self._open_redis()
            if self._postgres_required:
                await self._open_postgres()
            self.opened = True
        except Exception:
            await self.close()
            raise

    async def _open_redis(self) -> None:
        from ntheemba.infrastructure.redis.deduplication import RedisDeduplicationStore
        from ntheemba.infrastructure.redis.gateway import RedisReliableGatewayQueue
        from ntheemba.infrastructure.redis.idempotency import RedisIdempotencyStore
        from ntheemba.infrastructure.redis.keys import RedisKeyspace
        from ntheemba.infrastructure.redis.locking import RedisSessionLockManager
        from ntheemba.infrastructure.redis.runtime import RedisRuntime
        from ntheemba.infrastructure.redis.runtime_profiles import RedisRuntimeProfileCache
        from ntheemba.infrastructure.redis.sessions import RedisSessionRepository
        from ntheemba.infrastructure.redis.platform_sessions import (
            RedisPlatformSessionLockManager,
            RedisPlatformSessionRepository,
        )

        dsn = self.settings.redis_dsn
        if dsn is None:
            raise RuntimeError("Redis backend is configured without redis_url")
        runtime = RedisRuntime(
            dsn,
            socket_timeout=self.settings.redis_socket_timeout_seconds,
        )
        await runtime.open()
        self.redis_runtime = runtime
        keyspace = RedisKeyspace(
            self.settings.redis_key_prefix,
            self.settings.environment,
        )
        self.idempotency = RedisIdempotencyStore(runtime.client, keyspace)
        self.runtime_profile_cache = RedisRuntimeProfileCache(runtime.client, keyspace)
        if self.settings.session_backend == "redis":
            self.session_repository = RedisSessionRepository(
                runtime.client,
                keyspace,
                session_ttl=timedelta(seconds=self.settings.session_ttl_seconds),
                archive_ttl=timedelta(
                    seconds=self.settings.session_archive_ttl_seconds
                ),
            )
            self.session_locks = RedisSessionLockManager(
                runtime.client,
                keyspace,
                lock_ttl_seconds=self.settings.lock_ttl_seconds,
                retry_interval_seconds=self.settings.lock_retry_interval_seconds,
            )
            self.platform_session_repository = RedisPlatformSessionRepository(
                runtime.client,
                keyspace,
                session_ttl=timedelta(seconds=self.settings.session_ttl_seconds),
                archive_ttl=timedelta(seconds=self.settings.session_archive_ttl_seconds),
            )
            self.platform_session_locks = RedisPlatformSessionLockManager(
                runtime.client,
                keyspace,
                lock_ttl_seconds=self.settings.lock_ttl_seconds,
                retry_interval_seconds=self.settings.lock_retry_interval_seconds,
            )
            self.deduplication = RedisDeduplicationStore(runtime.client, keyspace)
        if self.settings.gateway_queue_backend == "redis":
            queue = RedisReliableGatewayQueue(
                runtime.client,
                keyspace,
                stream_max_length=self.settings.gateway_stream_max_length,
                claim_idle_seconds=self.settings.gateway_claim_idle_seconds,
            )
            await queue.initialize()
            self.gateway_queue = queue

    async def _open_postgres(self) -> None:
        from ntheemba.infrastructure.postgres.businesses import (
            PostgresBusinessRegistry,
            PostgresUnsupportedDeclarationSink,
        )
        from ntheemba.infrastructure.postgres.audit import PostgresAuditSink
        from ntheemba.infrastructure.postgres.customer_memory import (
            PostgresCustomerMemoryRepository,
        )
        from ntheemba.infrastructure.postgres.customers import PostgresCustomerDirectory
        from ntheemba.infrastructure.postgres.marketplace import PostgresMarketplaceRegistry
        from ntheemba.infrastructure.postgres.runtime import PostgresRuntime

        dsn = self.settings.postgres_connection_dsn
        if dsn is None:
            raise RuntimeError("PostgreSQL backend is configured without postgres_dsn")
        runtime = PostgresRuntime(
            dsn,
            min_size=self.settings.postgres_pool_min_size,
            max_size=self.settings.postgres_pool_max_size,
            timeout=self.settings.postgres_pool_timeout_seconds,
        )
        await runtime.open()
        self.postgres_runtime = runtime
        if self.settings.customer_backend == "postgres":
            self.customer_directory = PostgresCustomerDirectory(
                runtime.pool,
                default_country_code=self.settings.customer_default_country_code,
            )
            self.customer_memory_repository = PostgresCustomerMemoryRepository(
                runtime.pool
            )
        if self.settings.business_backend == "postgres":
            self.business_registry = PostgresBusinessRegistry(runtime.pool)
            self.unsupported_declarations = PostgresUnsupportedDeclarationSink(
                runtime.pool
            )
            self.audit_sink = PostgresAuditSink(runtime.pool)
            self.marketplace_registry = PostgresMarketplaceRegistry(runtime.pool)

    async def close(self) -> None:
        redis_runtime = self.redis_runtime
        postgres_runtime = self.postgres_runtime
        self.redis_runtime = None
        self.postgres_runtime = None
        self.opened = False
        if postgres_runtime is not None:
            await postgres_runtime.close()
        if redis_runtime is not None:
            await redis_runtime.close()

    async def snapshot(self) -> StorageSnapshot:
        redis_ready = not self._redis_required
        postgres_ready = not self._postgres_required
        details: list[str] = []
        if self.redis_runtime is not None:
            redis_ready = await self.redis_runtime.ping()
            details.append("Redis ready" if redis_ready else "Redis unavailable")
        elif self._redis_required:
            details.append("Redis not opened")
        else:
            details.append("Redis not required")
        if self.postgres_runtime is not None:
            postgres_ready = await self.postgres_runtime.ping()
            details.append(
                "PostgreSQL ready" if postgres_ready else "PostgreSQL unavailable"
            )
        elif self._postgres_required:
            details.append("PostgreSQL not opened")
        else:
            details.append("PostgreSQL not required")
        return StorageSnapshot(
            opened=self.opened,
            session_backend=self.settings.session_backend,
            customer_backend=self.settings.customer_backend,
            business_backend=self.settings.business_backend,
            gateway_queue_backend=self.settings.gateway_queue_backend,
            redis_ready=redis_ready,
            postgres_ready=postgres_ready,
            detail="; ".join(details),
        )

    @property
    def _redis_required(self) -> bool:
        return (
            self.settings.session_backend == "redis"
            or self.settings.gateway_queue_backend == "redis"
        )

    @property
    def _postgres_required(self) -> bool:
        return (
            self.settings.customer_backend == "postgres"
            or self.settings.business_backend == "postgres"
        )


def build_storage_runtime(settings: Settings) -> StorageRuntime:
    return StorageRuntime(settings)
