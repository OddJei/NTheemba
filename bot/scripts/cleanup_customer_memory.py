"""Delete expired PostgreSQL conversation memory and unsupported observations."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta

import psycopg

from ntheemba.runtime import run_async


async def cleanup(
    dsn: str,
    *,
    message_days: int,
    summary_days: int,
    question_days: int,
    unsupported_days: int,
) -> None:
    now = datetime.now(UTC)
    async with await psycopg.AsyncConnection.connect(dsn) as connection:
        cursor = await connection.execute(
            "SELECT * FROM cleanup_ntheemba_memory(%s, %s, %s, %s)",
            (
                now - timedelta(days=message_days),
                now - timedelta(days=summary_days),
                now - timedelta(days=question_days),
                now - timedelta(days=unsupported_days),
            ),
        )
        row = await cursor.fetchone()
        await connection.commit()
        print(
            {
                "messages_deleted": row[0] if row else 0,
                "summaries_deleted": row[1] if row else 0,
                "questions_deleted": row[2] if row else 0,
                "unsupported_observations_deleted": row[3] if row else 0,
            }
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--message-days", type=int, default=180)
    parser.add_argument("--summary-days", type=int, default=730)
    parser.add_argument("--question-days", type=int, default=730)
    parser.add_argument("--unsupported-days", type=int, default=365)
    args = parser.parse_args()
    run_async(
        cleanup(
            args.dsn,
            message_days=args.message_days,
            summary_days=args.summary_days,
            question_days=args.question_days,
            unsupported_days=args.unsupported_days,
        )
    )


if __name__ == "__main__":
    main()
