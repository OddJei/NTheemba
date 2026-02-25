"""add missing columns to business_subscriptions

Revision ID: 0007_add_business_subscriptions_columns_more
Revises: 0006_add_subscription_billing_interval
Create Date: 2026-02-23 00:45:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0007_add_business_subscriptions_columns_more'
down_revision = '0006_add_subscription_billing_interval'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add several columns used by the BusinessSubscription model if they don't exist.
    op.execute('''
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'msme_engine' AND table_name = 'business_subscriptions' AND column_name = 'start_date'
        ) THEN
            ALTER TABLE msme_engine.business_subscriptions ADD COLUMN start_date timestamptz NULL;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'msme_engine' AND table_name = 'business_subscriptions' AND column_name = 'end_date'
        ) THEN
            ALTER TABLE msme_engine.business_subscriptions ADD COLUMN end_date timestamptz NULL;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'msme_engine' AND table_name = 'business_subscriptions' AND column_name = 'periods_paid'
        ) THEN
            ALTER TABLE msme_engine.business_subscriptions ADD COLUMN periods_paid numeric(8,4) DEFAULT 0;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'msme_engine' AND table_name = 'business_subscriptions' AND column_name = 'paid_through'
        ) THEN
            ALTER TABLE msme_engine.business_subscriptions ADD COLUMN paid_through timestamptz NULL;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'msme_engine' AND table_name = 'business_subscriptions' AND column_name = 'created_at'
        ) THEN
            ALTER TABLE msme_engine.business_subscriptions ADD COLUMN created_at timestamptz DEFAULT now();
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'msme_engine' AND table_name = 'business_subscriptions' AND column_name = 'updated_at'
        ) THEN
            ALTER TABLE msme_engine.business_subscriptions ADD COLUMN updated_at timestamptz DEFAULT now();
        END IF;
    END$$;
    ''')


def downgrade() -> None:
    op.execute('''
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'msme_engine' AND table_name = 'business_subscriptions' AND column_name = 'start_date'
        ) THEN
            ALTER TABLE msme_engine.business_subscriptions DROP COLUMN start_date;
        END IF;

        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'msme_engine' AND table_name = 'business_subscriptions' AND column_name = 'end_date'
        ) THEN
            ALTER TABLE msme_engine.business_subscriptions DROP COLUMN end_date;
        END IF;

        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'msme_engine' AND table_name = 'business_subscriptions' AND column_name = 'periods_paid'
        ) THEN
            ALTER TABLE msme_engine.business_subscriptions DROP COLUMN periods_paid;
        END IF;

        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'msme_engine' AND table_name = 'business_subscriptions' AND column_name = 'paid_through'
        ) THEN
            ALTER TABLE msme_engine.business_subscriptions DROP COLUMN paid_through;
        END IF;

        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'msme_engine' AND table_name = 'business_subscriptions' AND column_name = 'created_at'
        ) THEN
            ALTER TABLE msme_engine.business_subscriptions DROP COLUMN created_at;
        END IF;

        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'msme_engine' AND table_name = 'business_subscriptions' AND column_name = 'updated_at'
        ) THEN
            ALTER TABLE msme_engine.business_subscriptions DROP COLUMN updated_at;
        END IF;
    END$$;
    ''')
