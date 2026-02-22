from sqlalchemy import create_engine, text
import os

url = os.environ.get('DATABASE_URL') or os.environ.get('DATABASE_URL'.upper())
if not url:
    raise SystemExit('DATABASE_URL env var not set')

# remove async driver suffix if present
sync_url = url.replace('+asyncpg', '').replace('+aiosqlite', '')
engine = create_engine(sync_url)
conn = engine.connect()
try:
    conn.execute(text("CREATE SCHEMA IF NOT EXISTS payment_revenue"))
    conn.execute(text("""
    CREATE TABLE IF NOT EXISTS payment_revenue.platform_fees (
        id varchar(36) PRIMARY KEY,
        deposit_id varchar(64),
        order_id varchar(64),
        currency varchar(8) NOT NULL DEFAULT 'ZMW',
        amount_minor integer NOT NULL DEFAULT 0,
        meta jsonb DEFAULT '{}'::jsonb,
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now()
    )
    """))
    conn.execute(text('CREATE INDEX IF NOT EXISTS ix_platform_fees_deposit_id ON payment_revenue.platform_fees (deposit_id)'))
    conn.execute(text('CREATE INDEX IF NOT EXISTS ix_platform_fees_order_id ON payment_revenue.platform_fees (order_id)'))

    # Add payout_type column safely
    conn.execute(text("ALTER TABLE IF EXISTS payment_revenue.pawapay_payouts ADD COLUMN IF NOT EXISTS payout_type varchar(32) DEFAULT 'msme'"))
    conn.execute(text("UPDATE payment_revenue.pawapay_payouts SET payout_type='msme' WHERE payout_type IS NULL"))
    conn.execute(text("ALTER TABLE payment_revenue.pawapay_payouts ALTER COLUMN payout_type SET NOT NULL"))

    print('migration_sql_applied')
finally:
    conn.close()
