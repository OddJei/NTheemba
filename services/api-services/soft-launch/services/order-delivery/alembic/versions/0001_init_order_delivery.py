"""initial order-delivery schema

Revision ID: 0001_init_order_delivery
Revises: 
Create Date: 2026-01-07 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_init_order_delivery'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'orders',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('session_id', sa.String(128), nullable=True),
        sa.Column('user_phone', sa.String(64), nullable=False, index=False),
        sa.Column('user_id', sa.String(36), nullable=True),
        sa.Column('business_id', sa.String(36), nullable=False),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('delivery_method', sa.String(32), nullable=False),
        sa.Column('total_amount', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(8), nullable=False),
        sa.Column('meta', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'deliveries',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('order_id', sa.String(36), nullable=False),
        sa.Column('user_phone', sa.String(64), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=True),
        sa.Column('business_id', sa.String(36), nullable=False),
        sa.Column('delivery_method', sa.String(32), nullable=False),
        sa.Column('delivery_code', sa.String(16), nullable=True),
        sa.Column('delivery_code_salt', sa.String(64), nullable=True),
        sa.Column('delivery_code_hash', sa.String(128), nullable=True),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('confirmed_by', sa.String(128), nullable=True),
        sa.Column('meta', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'outbox_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('event_type', sa.String(64), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('processed', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'idempotency_records',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('scope', sa.String(128), nullable=False),
        sa.Column('key', sa.String(128), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=False),
        sa.Column('response_body', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table('idempotency_records')
    op.drop_table('outbox_events')
    op.drop_table('deliveries')
    op.drop_table('orders')
