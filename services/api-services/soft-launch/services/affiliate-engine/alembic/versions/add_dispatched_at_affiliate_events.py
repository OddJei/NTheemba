"""add dispatched_at to affiliate_events

Revision ID: add_dispatched_at_affiliate_events
Revises: add_product_business_affiliate_links
Create Date: 2026-01-12

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "add_dispatched_at_affiliate_events"
down_revision = "add_product_business_affiliate_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    try:
        bind = op.get_bind()
        insp = inspect(bind)
        cols = {c["name"] for c in insp.get_columns("affiliate_events")}
        idx_names = {i["name"] for i in insp.get_indexes("affiliate_events")}
    except Exception:  # noqa: BLE001
        cols = set()
        idx_names = set()

    if "dispatched_at" not in cols:
        op.add_column("affiliate_events", sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True))

    idx = op.f("ix_affiliate_events_dispatched")
    if idx not in idx_names:
        op.create_index(idx, "affiliate_events", ["dispatched_at"], unique=False)


def downgrade() -> None:
    try:
        bind = op.get_bind()
        insp = inspect(bind)
        cols = {c["name"] for c in insp.get_columns("affiliate_events")}
        idx_names = {i["name"] for i in insp.get_indexes("affiliate_events")}
    except Exception:  # noqa: BLE001
        cols = set()
        idx_names = set()

    idx = op.f("ix_affiliate_events_dispatched")
    if idx in idx_names:
        op.drop_index(idx, table_name="affiliate_events")
    if "dispatched_at" in cols:
        op.drop_column("affiliate_events", "dispatched_at")
