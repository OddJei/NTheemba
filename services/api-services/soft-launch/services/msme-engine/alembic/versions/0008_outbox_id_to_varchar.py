"""Convert msme_engine.outbox_events.id from uuid -> varchar(36)

Revision ID: 0008_outbox_id_to_varchar
Revises: 0007_add_business_subscriptions_columns_more
Create Date: 2026-02-25 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0008_outbox_id_to_varchar'
down_revision = '0007_add_business_subscriptions_columns_more'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Convert column type from uuid to varchar(36) preserving values
    op.execute("""
    ALTER TABLE msme_engine.outbox_events
      ALTER COLUMN id TYPE varchar(36) USING id::text;
    """)


def downgrade() -> None:
    # Convert back to uuid type (best-effort)
    op.execute("""
    ALTER TABLE msme_engine.outbox_events
      ALTER COLUMN id TYPE uuid USING id::uuid;
    """)
