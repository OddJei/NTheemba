"""add affiliate_tokens table

Revision ID: add_affiliate_tokens
Revises: add_dispatched_at_affiliate_events
Create Date: 2026-01-23

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "add_affiliate_tokens"
down_revision = "add_dispatched_at_affiliate_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    try:
        bind = op.get_bind()
        insp = inspect(bind)
        has_table = insp.has_table("affiliate_tokens")
    except Exception:  # noqa: BLE001
        has_table = False

    if not has_table:
        op.create_table(
            "affiliate_tokens",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("token", sa.String(length=120), nullable=False),
            sa.Column("link_id", sa.String(length=36), nullable=False),
            sa.Column("affiliate_id", sa.String(length=36), nullable=False),
            sa.Column("product_id", sa.String(length=36), nullable=False),
            sa.Column("business_id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("meta", sa.JSON(), nullable=True),
            sa.UniqueConstraint("token", name="uq_affiliate_token"),
        )

    # Best-effort index creation (safe if they already exist)
    try:
        bind = op.get_bind()
        insp = inspect(bind)
        idx_names = {i["name"] for i in insp.get_indexes("affiliate_tokens")}
    except Exception:  # noqa: BLE001
        idx_names = set()

    token_idx = op.f("ix_affiliate_tokens_token")
    expires_idx = op.f("ix_affiliate_tokens_expires")
    if token_idx not in idx_names:
        op.create_index(token_idx, "affiliate_tokens", ["token"], unique=False)
    if expires_idx not in idx_names:
        op.create_index(expires_idx, "affiliate_tokens", ["expires_at"], unique=False)


def downgrade() -> None:
    try:
        bind = op.get_bind()
        insp = inspect(bind)
        has_table = insp.has_table("affiliate_tokens")
        idx_names = {i["name"] for i in insp.get_indexes("affiliate_tokens")} if has_table else set()
    except Exception:  # noqa: BLE001
        has_table = False
        idx_names = set()

    token_idx = op.f("ix_affiliate_tokens_token")
    expires_idx = op.f("ix_affiliate_tokens_expires")
    if expires_idx in idx_names:
        op.drop_index(expires_idx, table_name="affiliate_tokens")
    if token_idx in idx_names:
        op.drop_index(token_idx, table_name="affiliate_tokens")

    if has_table:
        op.drop_table("affiliate_tokens")
