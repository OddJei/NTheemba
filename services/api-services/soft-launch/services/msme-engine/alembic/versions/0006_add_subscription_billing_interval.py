"""add billing_interval to business_subscriptions

Revision ID: 0006_add_subscription_billing_interval
Revises: 0005_add_business_subscription_columns
Create Date: 2026-02-23 00:30:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0006_add_subscription_billing_interval'
down_revision = '0005_add_business_subscription_columns'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add `billing_interval` varchar(10) column to msme_engine.business_subscriptions
    # if it doesn't exist. Use raw SQL with an existence check for idempotence.
    op.execute('''
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'msme_engine' AND table_name = 'business_subscriptions' AND column_name = 'billing_interval'
        ) THEN
            ALTER TABLE msme_engine.business_subscriptions ADD COLUMN billing_interval varchar(10) DEFAULT 'monthly';
        END IF;
    END$$;
    ''')


def downgrade() -> None:
    op.execute('''
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'msme_engine' AND table_name = 'business_subscriptions' AND column_name = 'billing_interval'
        ) THEN
            ALTER TABLE msme_engine.business_subscriptions DROP COLUMN billing_interval;
        END IF;
    END$$;
    ''')
