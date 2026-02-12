"""noop (tables created in 001_create_ice_schema)

Revision ID: 0001_create_ice_tables
Revises: 001_create_ice_schema
Create Date: 2026-02-06
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_create_ice_tables"
down_revision = "001_create_ice_schema"
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
