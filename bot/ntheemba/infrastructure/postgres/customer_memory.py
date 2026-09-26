"""PostgreSQL privacy-scoped customer memory repository."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from ntheemba.domain.customer_memory import (
    ConsentType,
    ConversationMessage,
    ConversationSummary,
    CustomerAddress,
    CustomerConsent,
    CustomerPreference,
    CustomerQuestion,
    QuestionOutcome,
    RetentionResult,
)


class PostgresCustomerMemoryRepository:
    def __init__(self, pool: Any) -> None:
        self.pool = pool

    @asynccontextmanager
    async def _connection(self) -> AsyncIterator[Any]:
        async with self.pool.connection() as connection:
            async with connection.transaction():
                yield connection

    @asynccontextmanager
    async def _scope(self, business_id: str | None, customer_id: str) -> AsyncIterator[Any]:
        async with self._connection() as connection:
            await connection.execute(
                "SELECT set_config('app.business_id', %s, TRUE)", (business_id or "",)
            )
            await connection.execute(
                "SELECT set_config('app.customer_id', %s, TRUE)", (customer_id,)
            )
            yield connection

    async def get_consent(self, customer_id: str, consent_type: str) -> CustomerConsent | None:
        async with self._connection() as connection:
            cursor = await connection.execute(
                """
                SELECT customer_id, consent_type, granted, source, updated_at
                  FROM customer_consents
                 WHERE customer_id = %s AND consent_type = %s
                """,
                (customer_id, consent_type),
            )
            row = await cursor.fetchone()
        return None if row is None else self._consent(row)

    async def save_consent(self, consent: CustomerConsent) -> CustomerConsent:
        async with self._connection() as connection:
            cursor = await connection.execute(
                """
                INSERT INTO customer_consents (customer_id, consent_type, granted, source, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (customer_id, consent_type) DO UPDATE SET
                    granted = EXCLUDED.granted,
                    source = EXCLUDED.source,
                    updated_at = EXCLUDED.updated_at
                RETURNING customer_id, consent_type, granted, source, updated_at
                """,
                (
                    consent.customer_id,
                    consent.consent_type.value,
                    consent.granted,
                    consent.source,
                    consent.updated_at,
                ),
            )
            row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("PostgreSQL did not return consent")
        return self._consent(row)

    async def list_addresses(self, customer_id: str, *, business_id: str | None) -> tuple[CustomerAddress, ...]:
        async with self._scope(business_id, customer_id) as connection:
            cursor = await connection.execute(
                """
                SELECT address_id, customer_id, business_id, label, location_text,
                       is_default, created_at
                  FROM customer_addresses
                 WHERE customer_id = %s AND (business_id IS NULL OR business_id = %s)
                 ORDER BY is_default DESC, created_at DESC
                """,
                (customer_id, business_id),
            )
            rows = await cursor.fetchall()
        return tuple(self._address(row) for row in rows)

    async def save_address(self, address: CustomerAddress) -> CustomerAddress:
        async with self._scope(address.business_id, address.customer_id) as connection:
            if address.is_default:
                await connection.execute(
                    """
                    UPDATE customer_addresses SET is_default = FALSE
                     WHERE customer_id = %s AND business_id IS NOT DISTINCT FROM %s
                    """,
                    (address.customer_id, address.business_id),
                )
            cursor = await connection.execute(
                """
                INSERT INTO customer_addresses (
                    address_id, customer_id, business_id, label, location_text,
                    is_default, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (address_id) DO UPDATE SET
                    label = EXCLUDED.label,
                    location_text = EXCLUDED.location_text,
                    is_default = EXCLUDED.is_default
                RETURNING address_id, customer_id, business_id, label, location_text,
                          is_default, created_at
                """,
                (
                    address.address_id, address.customer_id, address.business_id,
                    address.label, address.location_text, address.is_default, address.created_at,
                ),
            )
            row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("PostgreSQL did not return address")
        return self._address(row)

    async def list_preferences(self, customer_id: str, *, business_id: str | None) -> tuple[CustomerPreference, ...]:
        async with self._scope(business_id, customer_id) as connection:
            cursor = await connection.execute(
                """
                SELECT preference_id, customer_id, business_id, preference_key,
                       preference_value, source, confirmed_at
                  FROM customer_preferences
                 WHERE customer_id = %s AND (business_id IS NULL OR business_id = %s)
                """,
                (customer_id, business_id),
            )
            rows = await cursor.fetchall()
        return tuple(self._preference(row) for row in rows)

    async def save_preference(self, preference: CustomerPreference) -> CustomerPreference:
        async with self._scope(preference.business_id, preference.customer_id) as connection:
            cursor = await connection.execute(
                """
                INSERT INTO customer_preferences (
                    preference_id, customer_id, business_id, preference_key,
                    preference_value, source, confirmed_at
                ) VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)
                ON CONFLICT (customer_id, business_id, preference_key) DO UPDATE SET
                    preference_value = EXCLUDED.preference_value,
                    source = EXCLUDED.source,
                    confirmed_at = EXCLUDED.confirmed_at
                RETURNING preference_id, customer_id, business_id, preference_key,
                          preference_value, source, confirmed_at
                """,
                (
                    preference.preference_id, preference.customer_id, preference.business_id,
                    preference.key, json.dumps(dict(preference.value)), preference.source,
                    preference.confirmed_at,
                ),
            )
            row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("PostgreSQL did not return preference")
        return self._preference(row)

    async def record_message(self, message: ConversationMessage) -> None:
        async with self._scope(message.business_id, message.customer_id) as connection:
            await connection.execute(
                """
                INSERT INTO conversation_messages (
                    message_id, conversation_id, business_id, customer_id,
                    sender_type, message_text, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (message_id) DO NOTHING
                """,
                (
                    message.message_id, message.conversation_id, message.business_id,
                    message.customer_id, message.sender_type, message.message_text,
                    message.created_at,
                ),
            )

    async def record_summary(self, summary: ConversationSummary) -> None:
        async with self._scope(summary.business_id, summary.customer_id) as connection:
            await connection.execute(
                """
                INSERT INTO conversation_summaries (
                    summary_id, conversation_id, business_id, customer_id,
                    intent, outcome, topic, follow_up_required, summary, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                ON CONFLICT (summary_id) DO NOTHING
                """,
                (
                    summary.summary_id, summary.conversation_id, summary.business_id,
                    summary.customer_id, summary.intent, summary.outcome, summary.topic,
                    summary.follow_up_required, json.dumps(dict(summary.summary)), summary.created_at,
                ),
            )

    async def record_question(self, question: CustomerQuestion) -> None:
        async with self._scope(question.business_id, question.customer_id) as connection:
            await connection.execute(
                """
                INSERT INTO customer_questions (
                    question_id, business_id, customer_id, conversation_id,
                    topic, question_text, outcome, required_handover, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (question_id) DO NOTHING
                """,
                (
                    question.question_id, question.business_id, question.customer_id,
                    question.conversation_id, question.topic, question.question_text,
                    question.outcome.value, question.required_handover, question.created_at,
                ),
            )

    async def list_summaries(self, business_id: str, customer_id: str, *, limit: int = 50) -> tuple[ConversationSummary, ...]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        async with self._scope(business_id, customer_id) as connection:
            cursor = await connection.execute(
                """
                SELECT summary_id, conversation_id, business_id, customer_id,
                       intent, outcome, topic, follow_up_required, summary, created_at
                  FROM conversation_summaries
                 WHERE business_id = %s AND customer_id = %s
                 ORDER BY created_at DESC LIMIT %s
                """,
                (business_id, customer_id, limit),
            )
            rows = await cursor.fetchall()
        return tuple(self._summary(row) for row in rows)

    async def list_questions(self, business_id: str, customer_id: str, *, limit: int = 50) -> tuple[CustomerQuestion, ...]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        async with self._scope(business_id, customer_id) as connection:
            cursor = await connection.execute(
                """
                SELECT question_id, business_id, customer_id, conversation_id,
                       topic, question_text, outcome, required_handover, created_at
                  FROM customer_questions
                 WHERE business_id = %s AND customer_id = %s
                 ORDER BY created_at DESC LIMIT %s
                """,
                (business_id, customer_id, limit),
            )
            rows = await cursor.fetchall()
        return tuple(self._question(row) for row in rows)

    async def delete_customer(self, customer_id: str) -> None:
        async with self._connection() as connection:
            await connection.execute("DELETE FROM customers WHERE customer_id = %s", (customer_id,))

    async def cleanup(self, *, message_cutoff: Any, summary_cutoff: Any, question_cutoff: Any, unsupported_cutoff: Any) -> RetentionResult:
        async with self._connection() as connection:
            cursor = await connection.execute(
                "SELECT * FROM cleanup_ntheemba_memory(%s, %s, %s, %s)",
                (message_cutoff, summary_cutoff, question_cutoff, unsupported_cutoff),
            )
            row = await cursor.fetchone()
        if row is None:
            return RetentionResult()
        return RetentionResult(
            messages_deleted=int(row["messages_deleted"]),
            summaries_deleted=int(row["summaries_deleted"]),
            questions_deleted=int(row["questions_deleted"]),
            unsupported_observations_deleted=int(row["unsupported_observations_deleted"]),
        )

    @staticmethod
    def _consent(row: Any) -> CustomerConsent:
        return CustomerConsent(
            customer_id=str(row["customer_id"]),
            consent_type=ConsentType(str(row["consent_type"])),
            granted=bool(row["granted"]),
            source=str(row["source"]),
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _address(row: Any) -> CustomerAddress:
        return CustomerAddress(
            address_id=str(row["address_id"]), customer_id=str(row["customer_id"]),
            business_id=None if row["business_id"] is None else str(row["business_id"]),
            label=str(row["label"]), location_text=str(row["location_text"]),
            is_default=bool(row["is_default"]), created_at=row["created_at"],
        )

    @staticmethod
    def _preference(row: Any) -> CustomerPreference:
        return CustomerPreference(
            preference_id=str(row["preference_id"]), customer_id=str(row["customer_id"]),
            business_id=None if row["business_id"] is None else str(row["business_id"]),
            key=str(row["preference_key"]), value=dict(row["preference_value"]),
            source=str(row["source"]), confirmed_at=row["confirmed_at"],
        )

    @staticmethod
    def _summary(row: Any) -> ConversationSummary:
        return ConversationSummary(
            summary_id=str(row["summary_id"]), conversation_id=str(row["conversation_id"]),
            business_id=str(row["business_id"]), customer_id=str(row["customer_id"]),
            intent=str(row["intent"]), outcome=str(row["outcome"]), topic=str(row["topic"] or ""),
            follow_up_required=bool(row["follow_up_required"]), summary=dict(row["summary"]),
            created_at=row["created_at"],
        )

    @staticmethod
    def _question(row: Any) -> CustomerQuestion:
        return CustomerQuestion(
            question_id=str(row["question_id"]), business_id=str(row["business_id"]),
            customer_id=str(row["customer_id"]), conversation_id=str(row["conversation_id"]),
            topic=str(row["topic"]), question_text=str(row["question_text"]),
            outcome=QuestionOutcome(str(row["outcome"])),
            required_handover=bool(row["required_handover"]), created_at=row["created_at"],
        )
