"""initial (baseline) migration for msme-engine

Revision ID: 0001_init_msme_engine
Revises: 
Create Date: 2026-01-19 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0001_init_msme_engine'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Baseline: DB already contains tables (created via create_all).
    # This migration is intentionally empty and is used to stamp the DB baseline.
    pass


def downgrade() -> None:
    pass
