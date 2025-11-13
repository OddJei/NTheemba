"""Migration script templates for Alembic."""
from alembic import op
import sqlalchemy as sa

revision = '${up_revision}'
down_revision = ${down_revision if down_revision else None}
branch_labels = ${branch_labels if branch_labels else None}
depends_on = ${depends_on if depends_on else None}

def upgrade():
    ${upgrades if upgrades else "pass"}


def downgrade():
    ${downgrades if downgrades else "pass"}
