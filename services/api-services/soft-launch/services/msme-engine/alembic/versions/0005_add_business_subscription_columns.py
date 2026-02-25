"""add subscription columns to businesses

Revision ID: 0005_add_business_subscription_columns
Revises: 0004_add_signed_terms_user
Create Date: 2026-02-23 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0005_add_business_subscription_columns'
down_revision = '0004_add_signed_terms_user'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add `subscription_price_minor` and `subscription_currency` columns to
    # msme_engine.businesses if they don't exist. Use raw SQL with an
    # existence check so the migration is safe to run multiple times.
    op.execute('''
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'msme_engine' AND table_name = 'businesses' AND column_name = 'subscription_price_minor'
        ) THEN
            ALTER TABLE msme_engine.businesses ADD COLUMN subscription_price_minor integer;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'msme_engine' AND table_name = 'businesses' AND column_name = 'subscription_currency'
        ) THEN
            ALTER TABLE msme_engine.businesses ADD COLUMN subscription_currency varchar(10);
        END IF;
    END$$;
    ''')


def downgrade() -> None:
    op.execute('''
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'msme_engine' AND table_name = 'businesses' AND column_name = 'subscription_price_minor'
        ) THEN
            ALTER TABLE msme_engine.businesses DROP COLUMN subscription_price_minor;
        END IF;

        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'msme_engine' AND table_name = 'businesses' AND column_name = 'subscription_currency'
        ) THEN
            ALTER TABLE msme_engine.businesses DROP COLUMN subscription_currency;
        END IF;
    END$$;
    ''')
