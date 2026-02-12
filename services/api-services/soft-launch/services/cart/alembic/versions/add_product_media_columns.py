"""Add product name and media URL columns to cart_items

Revision ID: add_product_media
Revises: eda2367a9b63
Create Date: 2026-02-01 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_product_media'
down_revision: Union[str, Sequence[str], None] = 'eda2367a9b63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('cart_items', sa.Column('product_name', sa.String(), nullable=True))
    op.add_column('cart_items', sa.Column('media_url', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('cart_items', 'media_url')
    op.drop_column('cart_items', 'product_name')
