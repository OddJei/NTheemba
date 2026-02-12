"""add delivery_locations jsonb column to businesses

Revision ID: 0003_add_delivery_locations_json
Revises: 0002_alter_msme_events_event_id
Create Date: 2026-02-10 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0003_add_delivery_locations_json'
down_revision = '0002_alter_msme_events_event_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # For Postgres ensure column exists as JSONB (best-effort). Use raw SQL so it's idempotent.
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'msme_engine' AND table_name = 'businesses' AND column_name = 'delivery_locations'
        ) THEN
            ALTER TABLE msme_engine.businesses ADD COLUMN delivery_locations JSONB;
        END IF;
    END$$;
    """)


def downgrade() -> None:
    # Drop the column if it exists
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'msme_engine' AND table_name = 'businesses' AND column_name = 'delivery_locations'
        ) THEN
            ALTER TABLE msme_engine.businesses DROP COLUMN delivery_locations;
        END IF;
    END$$;
    """)
