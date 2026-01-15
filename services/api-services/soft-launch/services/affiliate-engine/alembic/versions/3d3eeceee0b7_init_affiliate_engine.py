"""init affiliate engine

Revision ID: 3d3eeceee0b7
Revises: 
Create Date: 2026-01-07 07:30:50.602267

"""
from typing import Sequence, Union

from alembic import op



# revision identifiers, used by Alembic.
revision: str = '3d3eeceee0b7'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create tables from the current SQLAlchemy metadata.
    # Subsequent migrations in this service are written to be idempotent (they skip if columns already exist),
    # so it's safe for this baseline to create the latest schema on new databases.
    bind = op.get_bind()
    from src.app.db import Base  # imported here so Alembic has sys.path set (see env.py)
    import src.app.models  # noqa: F401  (ensure models are registered on Base.metadata)

    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    from src.app.db import Base
    import src.app.models  # noqa: F401

    Base.metadata.drop_all(bind=bind)
