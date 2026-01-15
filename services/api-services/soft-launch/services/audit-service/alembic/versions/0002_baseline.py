"""baseline revision to record current DB state

Revision ID: 0002_baseline
Revises: 0001_create_audit_logs
Create Date: 2025-11-05 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0002_baseline'
down_revision = '0001_create_audit_logs'
branch_labels = None
depends_on = None


def upgrade():
    # This is a baseline/empty migration. The schema and tables were already created
    # by `init_db()` during development; this migration records the current state.
    pass


def downgrade():
    # No-op: do not drop tables in downgrade for baseline.
    pass
