"""create ice service schema

Revision ID: 001_create_ice_schema
Revises: 
Create Date: 2026-02-06 00:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "001_create_ice_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    schema = op.get_context().opts.get("version_table_schema", "ice_service")

    op.create_table(
        "ice_sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("phone_number", sa.String(), nullable=False),
        sa.Column("business_id", sa.String(), nullable=False),
        sa.Column("blob", sa.JSON(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("session_id", name="uq_ice_sessions_session_id"),
        schema=schema,
    )
    op.create_index("ix_ice_sessions_business_id", "ice_sessions", ["business_id"], schema=schema)
    op.create_index("ix_ice_sessions_phone_number", "ice_sessions", ["phone_number"], schema=schema)
    op.create_index("ix_ice_sessions_session_id", "ice_sessions", ["session_id"], schema=schema)

    op.create_table(
        "ice_order_drafts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("order_id", sa.String(), nullable=True),
        sa.Column("blob", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("schema_version", sa.String(), nullable=True),
        sa.Column("idempotency_key", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("idempotency_key", name="uq_ice_order_drafts_idempotency"),
        schema=schema,
    )
    op.create_index("ix_ice_order_drafts_session_id", "ice_order_drafts", ["session_id"], schema=schema)
    op.create_index("ix_ice_order_drafts_order_id", "ice_order_drafts", ["order_id"], schema=schema)

    op.create_table(
        "ice_product_snapshots",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("business_id", sa.String(), nullable=False),
        sa.Column("product_id", sa.String(), nullable=False),
        sa.Column("variant_id", sa.String(), nullable=True),
        sa.Column("blob", sa.JSON(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        schema=schema,
    )
    op.create_index("ix_product_snapshots_business_product", "ice_product_snapshots", ["business_id", "product_id"], schema=schema)
    op.create_index("ix_ice_product_snapshots_business_id", "ice_product_snapshots", ["business_id"], schema=schema)
    op.create_index("ix_ice_product_snapshots_product_id", "ice_product_snapshots", ["product_id"], schema=schema)
    op.create_index("ix_ice_product_snapshots_variant_id", "ice_product_snapshots", ["variant_id"], schema=schema)

    op.create_table(
        "ice_catalog_snapshots",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("business_id", sa.String(), nullable=False),
        sa.Column("blob", sa.JSON(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("business_id", name="uq_ice_catalog_snapshots_business_id"),
        schema=schema,
    )
    op.create_index("ix_ice_catalog_snapshots_business_id", "ice_catalog_snapshots", ["business_id"], schema=schema)

    op.create_table(
        "ice_affiliate_contexts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("order_id", sa.String(), nullable=True),
        sa.Column("affiliate_id", sa.String(), nullable=True),
        sa.Column("blob", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("schema_version", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        schema=schema,
    )
    op.create_index("ix_ice_affiliate_contexts_session_id", "ice_affiliate_contexts", ["session_id"], schema=schema)
    op.create_index("ix_ice_affiliate_contexts_order_id", "ice_affiliate_contexts", ["order_id"], schema=schema)
    op.create_index("ix_ice_affiliate_contexts_affiliate_id", "ice_affiliate_contexts", ["affiliate_id"], schema=schema)

    op.create_table(
        "ice_audit_logs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("order_id", sa.String(), nullable=True),
        sa.Column("business_id", sa.String(), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("event_payload", sa.JSON(), nullable=True),
        sa.Column("correlation_id", sa.String(), nullable=True),
        sa.Column("idempotency_key", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema=schema,
    )
    op.create_index("ix_audit_logs_session_id", "ice_audit_logs", ["session_id"], schema=schema)
    op.create_index("ix_audit_logs_event_type", "ice_audit_logs", ["event_type"], schema=schema)
    op.create_index("ix_audit_logs_created_at", "ice_audit_logs", ["created_at"], schema=schema)
    op.create_index("ix_ice_audit_logs_order_id", "ice_audit_logs", ["order_id"], schema=schema)
    op.create_index("ix_ice_audit_logs_business_id", "ice_audit_logs", ["business_id"], schema=schema)

    op.create_table(
        "ice_idempotency_cache",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("request_method", sa.String(), nullable=False),
        sa.Column("request_path", sa.String(), nullable=False),
        sa.Column("response_status", sa.String(), nullable=False),
        sa.Column("response_body", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_ice_idempotency_key"),
        schema=schema,
    )
    op.create_index("ix_ice_idempotency_key", "ice_idempotency_cache", ["idempotency_key"], schema=schema)


def downgrade():
    schema = op.get_context().opts.get("version_table_schema", "ice_service")

    op.drop_table("ice_idempotency_cache", schema=schema)
    op.drop_table("ice_audit_logs", schema=schema)
    op.drop_table("ice_affiliate_contexts", schema=schema)
    op.drop_table("ice_catalog_snapshots", schema=schema)
    op.drop_table("ice_product_snapshots", schema=schema)
    op.drop_table("ice_order_drafts", schema=schema)
    op.drop_table("ice_sessions", schema=schema)
