"""add product and business columns to affiliate_links

Revision ID: add_product_business_affiliate_links
Revises: 3d3eeceee0b7
Create Date: 2026-01-07
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_product_business_affiliate_links'
down_revision = '3d3eeceee0b7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('affiliate_links', sa.Column('product_id', sa.String(length=36), nullable=True))
    op.add_column('affiliate_links', sa.Column('business_id', sa.String(length=36), nullable=True))
    op.create_index(op.f('ix_affiliate_links_product_id'), 'affiliate_links', ['product_id'], unique=False)
    op.create_index(op.f('ix_affiliate_links_business_id'), 'affiliate_links', ['business_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_affiliate_links_business_id'), table_name='affiliate_links')
    op.drop_index(op.f('ix_affiliate_links_product_id'), table_name='affiliate_links')
    op.drop_column('affiliate_links', 'business_id')
    op.drop_column('affiliate_links', 'product_id')
