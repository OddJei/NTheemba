"""
Revision script template for Alembic.
This is a standard template used by alembic when creating new revision files.
"""
<%text>
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '${up_revision}'
down_revision = ${down_revision!r}
branch_labels = ${branch_labels!r}
depend_on = ${depends_on!r}
</%text>

from alembic import op
import sqlalchemy as sa


def upgrade():
    ${upgrades if upgrades else "pass"}


def downgrade():
    ${downgrades if downgrades else "pass"}
