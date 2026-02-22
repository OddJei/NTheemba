"""add affiliate preferences, signed_terms, about columns

Revision ID: add_affiliate_preferences_signed_terms_about
Revises: autogen_20260125_1
Create Date: 2026-02-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "add_affiliate_preferences_signed_terms_about"
down_revision = "autogen_20260125_1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    try:
        insp = inspect(bind)
        has_table = insp.has_table("affiliates")
    except Exception:
        has_table = False

    if not has_table:
        # If the base table doesn't exist, create all metadata (safe for fresh DBs)
        from src.app.db import Base
        import src.app.models  # noqa: F401

        Base.metadata.create_all(bind=bind)
        return

    # Get existing column names for idempotency checks
    try:
        existing_cols = {c["name"] for c in insp.get_columns("affiliates")}
    except Exception:
        existing_cols = set()

    if "preferences" not in existing_cols:
        # Use generic JSON column (works for Postgres and SQLite/others)
        op.add_column("affiliates", sa.Column("preferences", sa.JSON(), nullable=True))

    if "signed_terms" not in existing_cols:
        op.add_column("affiliates", sa.Column("signed_terms", sa.Boolean(), nullable=False, server_default=sa.text("false")))

    if "about" not in existing_cols:
        op.add_column("affiliates", sa.Column("about", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    try:
        insp = inspect(bind)
        has_table = insp.has_table("affiliates")
    except Exception:
        has_table = False

    if not has_table:
        return

    try:
        cols = {c["name"] for c in insp.get_columns("affiliates")}
    except Exception:
        cols = set()

    if "about" in cols:
        op.drop_column("affiliates", "about")
    if "signed_terms" in cols:
        op.drop_column("affiliates", "signed_terms")
    if "preferences" in cols:
        op.drop_column("affiliates", "preferences")
