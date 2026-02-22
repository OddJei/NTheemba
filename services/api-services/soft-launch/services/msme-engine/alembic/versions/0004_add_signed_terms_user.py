"""add signed_terms column to users

Revision ID: 0004_add_signed_terms_user
Revises: 0003_add_delivery_locations_json
Create Date: 2026-02-21 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0004_add_signed_terms_user'
down_revision = '0003_add_delivery_locations_json'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add `signed_terms` boolean column to msme_engine.users if it doesn't exist.
    # Use raw SQL and an existence check so this migration is idempotent when run
    # against an existing DB that may already have the column.
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'msme_engine' AND table_name = 'users' AND column_name = 'signed_terms'
        ) THEN
            ALTER TABLE msme_engine.users ADD COLUMN signed_terms boolean DEFAULT false NOT NULL;
        END IF;
    END$$;
    """)


def downgrade() -> None:
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'msme_engine' AND table_name = 'users' AND column_name = 'signed_terms'
        ) THEN
            ALTER TABLE msme_engine.users DROP COLUMN signed_terms;
        END IF;
    END$$;
    """)
