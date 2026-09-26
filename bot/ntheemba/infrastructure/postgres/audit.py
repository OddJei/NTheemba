"""PostgreSQL structured operational audit persistence."""

from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from ntheemba.ports.audit import AuditEvent


class PostgresAuditSink:
    """Persist redacted audit events into the operational audit ledger."""

    def __init__(self, pool: Any) -> None:
        self.pool = pool

    async def record(self, event: AuditEvent) -> None:
        await self.record_many((event,))

    async def record_many(self, events: tuple[AuditEvent, ...]) -> None:
        if not events:
            return
        async with self.pool.connection() as connection:
            async with connection.transaction():
                for event in events:
                    await connection.execute(
                        "SELECT set_config('app.business_id', %s, true)",
                        (event.business_id,),
                    )
                    await connection.execute(
                        """
                        INSERT INTO operational_audit_events (
                            event_id, event_type, request_id, business_id, severity,
                            conversation_id, message_id, occurred_at, data
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                        ON CONFLICT (event_id) DO NOTHING
                        """,
                        (
                            event.event_id,
                            event.event_type,
                            event.request_id,
                            event.business_id,
                            event.severity.value,
                            event.conversation_id,
                            event.message_id,
                            event.occurred_at,
                            Jsonb(dict(event.data)),
                        ),
                    )
