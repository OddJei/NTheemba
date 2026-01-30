import os
import sys
from urllib.parse import urlparse
import psycopg2

# Uses the same Postgres credentials used elsewhere in the repo.
DB_URL = "postgresql://postgres:!ladybug!%23!@127.0.0.1:5432/ntheemba"
REVISION = 'c4292361a706'


def connect():
    parsed = urlparse(DB_URL)
    user = parsed.username
    password = (parsed.password or '').replace('%23', '#')
    host = parsed.hostname or '127.0.0.1'
    port = parsed.port or 5432
    dbname = parsed.path.lstrip('/')
    return psycopg2.connect(user=user, password=password, host=host, port=port, dbname=dbname)


DDL = [
    "CREATE SCHEMA IF NOT EXISTS payment_revenue",
    # idempotency_records
    '''CREATE TABLE IF NOT EXISTS payment_revenue.idempotency_records (
        id VARCHAR(36) PRIMARY KEY,
        scope VARCHAR(128) NOT NULL,
        key VARCHAR(128) NOT NULL,
        status_code INTEGER NOT NULL,
        response_body JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL
    )''',
    "CREATE INDEX IF NOT EXISTS ix_idempotency_records_key ON payment_revenue.idempotency_records (key)",
    "CREATE INDEX IF NOT EXISTS ix_idempotency_records_scope ON payment_revenue.idempotency_records (scope)",
    # outbox
    '''CREATE TABLE IF NOT EXISTS payment_revenue.outbox (
        id VARCHAR(36) PRIMARY KEY,
        topic VARCHAR(64) NOT NULL,
        destination VARCHAR(256) NOT NULL,
        payload JSONB NOT NULL,
        status VARCHAR(32) NOT NULL,
        attempts INTEGER NOT NULL,
        last_error VARCHAR(512),
        send_after TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL
    )''',
    "CREATE INDEX IF NOT EXISTS ix_outbox_topic ON payment_revenue.outbox (topic)",
    # pawapay_deposits
    '''CREATE TABLE IF NOT EXISTS payment_revenue.pawapay_deposits (
        id VARCHAR(36) PRIMARY KEY,
        deposit_id VARCHAR(64) NOT NULL UNIQUE,
        order_id VARCHAR(64),
        business_id VARCHAR(64),
        currency VARCHAR(8) NOT NULL,
        amount_minor INTEGER NOT NULL,
        phone_number VARCHAR(32),
        provider VARCHAR(32),
        status VARCHAR(32) NOT NULL,
        failure_code VARCHAR(64),
        failure_message VARCHAR(256),
        meta JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL
    )''',
    "CREATE INDEX IF NOT EXISTS ix_pawapay_deposits_business_id ON payment_revenue.pawapay_deposits (business_id)",
    "CREATE INDEX IF NOT EXISTS ix_pawapay_deposits_deposit_id ON payment_revenue.pawapay_deposits (deposit_id)",
    "CREATE INDEX IF NOT EXISTS ix_pawapay_deposits_order_id ON payment_revenue.pawapay_deposits (order_id)",
    # pawapay_payouts
    '''CREATE TABLE IF NOT EXISTS payment_revenue.pawapay_payouts (
        id VARCHAR(36) PRIMARY KEY,
        payout_id VARCHAR(64) NOT NULL UNIQUE,
        order_id VARCHAR(64),
        business_id VARCHAR(64),
        currency VARCHAR(8) NOT NULL,
        amount_minor INTEGER NOT NULL,
        phone_number VARCHAR(32),
        provider VARCHAR(32),
        status VARCHAR(32) NOT NULL,
        failure_code VARCHAR(64),
        failure_message VARCHAR(256),
        meta JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL
    )''',
    "CREATE INDEX IF NOT EXISTS ix_pawapay_payouts_business_id ON payment_revenue.pawapay_payouts (business_id)",
    "CREATE INDEX IF NOT EXISTS ix_pawapay_payouts_order_id ON payment_revenue.pawapay_payouts (order_id)",
    "CREATE INDEX IF NOT EXISTS ix_pawapay_payouts_payout_id ON payment_revenue.pawapay_payouts (payout_id)",
    # pawapay_refunds
    '''CREATE TABLE IF NOT EXISTS payment_revenue.pawapay_refunds (
        id VARCHAR(36) PRIMARY KEY,
        refund_id VARCHAR(64) NOT NULL UNIQUE,
        deposit_id VARCHAR(64),
        order_id VARCHAR(64),
        business_id VARCHAR(64),
        currency VARCHAR(8) NOT NULL,
        amount_minor INTEGER NOT NULL,
        status VARCHAR(32) NOT NULL,
        failure_code VARCHAR(64),
        failure_message VARCHAR(256),
        meta JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL
    )''',
    "CREATE INDEX IF NOT EXISTS ix_pawapay_refunds_business_id ON payment_revenue.pawapay_refunds (business_id)",
    "CREATE INDEX IF NOT EXISTS ix_pawapay_refunds_deposit_id ON payment_revenue.pawapay_refunds (deposit_id)",
    "CREATE INDEX IF NOT EXISTS ix_pawapay_refunds_order_id ON payment_revenue.pawapay_refunds (order_id)",
    "CREATE INDEX IF NOT EXISTS ix_pawapay_refunds_refund_id ON payment_revenue.pawapay_refunds (refund_id)",
    # payouts
    '''CREATE TABLE IF NOT EXISTS payment_revenue.payouts (
        id VARCHAR(36) PRIMARY KEY,
        order_id VARCHAR(64) NOT NULL,
        payment_id VARCHAR(64) NOT NULL,
        business_id VARCHAR(64) NOT NULL,
        payee_type VARCHAR(32) NOT NULL,
        payee_id VARCHAR(64),
        currency VARCHAR(8) NOT NULL,
        amount_minor INTEGER NOT NULL,
        status VARCHAR(32) NOT NULL,
        meta JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL
    )''',
    "CREATE INDEX IF NOT EXISTS ix_payouts_business_id ON payment_revenue.payouts (business_id)",
    "CREATE INDEX IF NOT EXISTS ix_payouts_order_id ON payment_revenue.payouts (order_id)",
    "CREATE INDEX IF NOT EXISTS ix_payouts_payee_id ON payment_revenue.payouts (payee_id)",
    "CREATE INDEX IF NOT EXISTS ix_payouts_payee_type ON payment_revenue.payouts (payee_type)",
    "CREATE INDEX IF NOT EXISTS ix_payouts_payment_id ON payment_revenue.payouts (payment_id)",
    # settlements
    '''CREATE TABLE IF NOT EXISTS payment_revenue.settlements (
        id VARCHAR(36) PRIMARY KEY,
        order_id VARCHAR(64) NOT NULL,
        payment_id VARCHAR(64) NOT NULL,
        business_id VARCHAR(64) NOT NULL,
        currency VARCHAR(8) NOT NULL,
        amount_minor INTEGER NOT NULL,
        fee_bps INTEGER NOT NULL,
        platform_fee_minor INTEGER NOT NULL,
        affiliate_commission_minor INTEGER NOT NULL,
        msme_net_minor INTEGER NOT NULL,
        status VARCHAR(32) NOT NULL,
        dispatched BOOLEAN NOT NULL,
        meta JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL
    )''',
    "CREATE INDEX IF NOT EXISTS ix_settlements_business_id ON payment_revenue.settlements (business_id)",
    "CREATE INDEX IF NOT EXISTS ix_settlements_order_id ON payment_revenue.settlements (order_id)",
    "CREATE INDEX IF NOT EXISTS ix_settlements_payment_id ON payment_revenue.settlements (payment_id)",
    # subscription_payments
    '''CREATE TABLE IF NOT EXISTS payment_revenue.subscription_payments (
        id VARCHAR(36) PRIMARY KEY,
        payment_id VARCHAR(64) NOT NULL,
        business_id VARCHAR(64) NOT NULL,
        plan VARCHAR(32) NOT NULL,
        paid_until TIMESTAMPTZ NOT NULL,
        currency VARCHAR(8) NOT NULL,
        amount_minor INTEGER NOT NULL,
        status VARCHAR(32) NOT NULL,
        dispatched BOOLEAN NOT NULL,
        meta JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL
    )''',
    "CREATE INDEX IF NOT EXISTS ix_subscription_payments_business_id ON payment_revenue.subscription_payments (business_id)",
    "CREATE INDEX IF NOT EXISTS ix_subscription_payments_payment_id ON payment_revenue.subscription_payments (payment_id)",
]


def main():
    conn = connect()
    cur = conn.cursor()
    for stmt in DDL:
        cur.execute(stmt)
    # ensure alembic_version exists in payment_revenue and is stamped
    cur.execute("CREATE TABLE IF NOT EXISTS payment_revenue.alembic_version (version_num VARCHAR(32) PRIMARY KEY)")
    cur.execute("SELECT version_num FROM payment_revenue.alembic_version WHERE version_num=%s", (REVISION,))
    if cur.fetchone() is None:
        cur.execute("INSERT INTO payment_revenue.alembic_version (version_num) VALUES (%s)", (REVISION,))
    conn.commit()
    cur.close()
    conn.close()
    print('Domain tables and alembic_version stamped in payment_revenue')


if __name__ == '__main__':
    main()
