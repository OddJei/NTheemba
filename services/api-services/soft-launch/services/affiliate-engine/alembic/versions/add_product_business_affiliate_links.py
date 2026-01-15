"""add product and business columns to affiliate_links

Revision ID: add_product_business_affiliate_links
Revises: 3d3eeceee0b7
Create Date: 2026-01-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = 'add_product_business_affiliate_links'
down_revision = '3d3eeceee0b7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    try:
        bind = op.get_bind()
        insp = inspect(bind)
        cols = {c["name"] for c in insp.get_columns("affiliate_links")}
        idx_names = {i["name"] for i in insp.get_indexes("affiliate_links")}
    except Exception:  # noqa: BLE001
        cols = set()
        idx_names = set()

    if "product_id" not in cols:
        op.add_column("affiliate_links", sa.Column("product_id", sa.String(length=36), nullable=True))
    if "business_id" not in cols:
        op.add_column("affiliate_links", sa.Column("business_id", sa.String(length=36), nullable=True))

    product_idx = op.f("ix_affiliate_links_product_id")
    business_idx = op.f("ix_affiliate_links_business_id")
    if product_idx not in idx_names:
        op.create_index(product_idx, "affiliate_links", ["product_id"], unique=False)
    if business_idx not in idx_names:
        op.create_index(business_idx, "affiliate_links", ["business_id"], unique=False)


def downgrade() -> None:
    # Best-effort downgrade.
    try:
        bind = op.get_bind()
        insp = inspect(bind)
        cols = {c["name"] for c in insp.get_columns("affiliate_links")}
        idx_names = {i["name"] for i in insp.get_indexes("affiliate_links")}
    except Exception:  # noqa: BLE001
        cols = set()
        idx_names = set()

    business_idx = op.f("ix_affiliate_links_business_id")
    product_idx = op.f("ix_affiliate_links_product_id")
    if business_idx in idx_names:
        op.drop_index(business_idx, table_name="affiliate_links")
    if product_idx in idx_names:
        op.drop_index(product_idx, table_name="affiliate_links")
    if "business_id" in cols:
        op.drop_column("affiliate_links", "business_id")
    if "product_id" in cols:
        op.drop_column("affiliate_links", "product_id")
