"""increase msme_events.event_id length to 255

Revision ID: 0002_alter_msme_events_event_id
Revises: 0001_init_msme_engine
Create Date: 2026-01-20 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0002_alter_msme_events_event_id'
down_revision = '0001_init_msme_engine'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        'msme_events',
        'event_id',
        existing_type=sa.String(length=80),
        type_=sa.String(length=255),
        schema='msme_engine',
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        'msme_events',
        'event_id',
        existing_type=sa.String(length=255),
        type_=sa.String(length=80),
        schema='msme_engine',
        existing_nullable=False,
    )
