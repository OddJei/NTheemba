#!/usr/bin/env python3
"""Generic DB migration helper. Supports Postgres and SQLite via SQLAlchemy.

Usage: python migrate_db.py --database-url <DATABASE_URL>
If `DATABASE_URL` is not provided, the `DATABASE_URL` env var is used.
"""
import argparse
import os
import sys
from sqlalchemy import create_engine, text


MIGRATION_STEPS = [
    "add_signed_terms",
    "add_affiliate_id",
    "add_subscription_price_minor",
    "create_outbox_events_table",
]


def run_sql(conn, sql, params=None):
    print('EXEC:', sql.strip())
    conn.execute(text(sql), params or {})


def migrate(engine):
    url = str(engine.url)
    is_sqlite = url.startswith('sqlite')
    is_postgres = url.startswith('postgres') or url.startswith('postgresql')

    with engine.begin() as conn:
        # If Postgres, ensure we're operating in the msme_engine schema
        if is_postgres:
            run_sql(conn, "CREATE SCHEMA IF NOT EXISTS msme_engine")
            run_sql(conn, "SET search_path TO msme_engine")

        # users.signed_terms
        if is_postgres:
            run_sql(conn, "ALTER TABLE users ADD COLUMN IF NOT EXISTS signed_terms BOOLEAN DEFAULT FALSE")
        elif is_sqlite:
            # SQLite: use ALTER TABLE ADD COLUMN but only if missing (SQLAlchemy cannot check easily here)
            try:
                run_sql(conn, "ALTER TABLE users ADD COLUMN signed_terms INTEGER DEFAULT 0")
            except Exception:
                print('users.signed_terms may already exist or cannot be added on sqlite')

        # businesses.affiliate_id
        if is_postgres:
            run_sql(conn, "ALTER TABLE businesses ADD COLUMN IF NOT EXISTS affiliate_id TEXT")
        elif is_sqlite:
            try:
                run_sql(conn, "ALTER TABLE businesses ADD COLUMN affiliate_id TEXT")
            except Exception:
                print('businesses.affiliate_id may already exist or cannot be added on sqlite')

        # businesses.subscription_price_minor
        if is_postgres:
            run_sql(conn, "ALTER TABLE businesses ADD COLUMN IF NOT EXISTS subscription_price_minor INTEGER")
        elif is_sqlite:
            try:
                run_sql(conn, "ALTER TABLE businesses ADD COLUMN subscription_price_minor INTEGER")
            except Exception:
                print('businesses.subscription_price_minor may already exist or cannot be added on sqlite')

        # outbox_events table
        if is_postgres:
            # create schema if missing, then create table
            run_sql(conn, "CREATE SCHEMA IF NOT EXISTS msme_engine")
            run_sql(conn, """
            CREATE TABLE IF NOT EXISTS msme_engine.outbox_events (
                id TEXT PRIMARY KEY,
                topic TEXT,
                destination TEXT,
                target TEXT,
                payload TEXT,
                dedupe_key TEXT,
                attempts INTEGER DEFAULT 0,
                scheduled_at TIMESTAMP NULL,
                correlation_id TEXT,
                status TEXT,
                created_at TIMESTAMP DEFAULT now()
            )
            """)
        elif is_sqlite:
            # SQLite: create a table in default schema
            run_sql(conn, """
            CREATE TABLE IF NOT EXISTS outbox_events (
                id TEXT PRIMARY KEY,
                topic TEXT,
                destination TEXT,
                target TEXT,
                payload TEXT,
                dedupe_key TEXT,
                attempts INTEGER DEFAULT 0,
                scheduled_at TEXT NULL,
                correlation_id TEXT,
                status TEXT,
                created_at TEXT
            )
            """)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--database-url', dest='database_url', help='SQLAlchemy database URL')
    args = parser.parse_args(argv)
    database_url = args.database_url or os.environ.get('DATABASE_URL') or os.environ.get('OUTBOX_DATABASE_URL')
    if not database_url:
        print('Provide --database-url or set DATABASE_URL environment variable')
        sys.exit(2)

    print('Using database:', database_url)
    engine = create_engine(database_url)
    migrate(engine)
    print('Migration complete')


if __name__ == '__main__':
    main()
