"""add_media_urls_to_products

Revision ID: 79cfe2d405a4
Revises: 05bf32a2034a
Create Date: 2026-02-01 09:09:04.020887

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '79cfe2d405a4'
down_revision: Union[str, Sequence[str], None] = '05bf32a2034a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'products',
        sa.Column('media_urls', sa.JSON(), nullable=True),
        schema='catalog_inventory'
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('products', 'media_urls', schema='catalog_inventory')
