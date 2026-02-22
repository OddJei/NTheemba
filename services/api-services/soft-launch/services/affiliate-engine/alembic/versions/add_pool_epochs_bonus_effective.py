"""add pool_epochs bonus_pool_zmw and effective_pool_zmw

Revision ID: add_pool_epochs_bonus_effective
Revises: add_affiliate_preferences_signed_terms_about
Create Date: 2026-02-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "add_pool_epochs_bonus_effective"
down_revision = "add_affiliate_preferences_signed_terms_about"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    try:
        insp = inspect(bind)
        has_table = insp.has_table("pool_epochs")
    except Exception:
        has_table = False

    if not has_table:
        # If table missing, no-op (assume baseline migration will create it)
        return

    try:
        existing = {c["name"] for c in insp.get_columns("pool_epochs")}
    except Exception:
        existing = set()

    if "bonus_pool_zmw" not in existing:
        op.add_column("pool_epochs", sa.Column("bonus_pool_zmw", sa.Float(), nullable=False, server_default=sa.text("0.0")))

    if "effective_pool_zmw" not in existing:
        op.add_column("pool_epochs", sa.Column("effective_pool_zmw", sa.Float(), nullable=False, server_default=sa.text("0.0")))


def downgrade() -> None:
    bind = op.get_bind()
    try:
        insp = inspect(bind)
        has_table = insp.has_table("pool_epochs")
    except Exception:
        has_table = False

    if not has_table:
        return

    try:
        cols = {c["name"] for c in insp.get_columns("pool_epochs")}
    except Exception:
        cols = set()

    if "effective_pool_zmw" in cols:
        op.drop_column("pool_epochs", "effective_pool_zmw")
    if "bonus_pool_zmw" in cols:
        op.drop_column("pool_epochs", "bonus_pool_zmw")
