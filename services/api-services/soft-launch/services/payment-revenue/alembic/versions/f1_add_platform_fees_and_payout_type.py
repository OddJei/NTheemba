"""Add platform_fees table and payout_type to pawapay_payouts

Revision ID: f1_add_platform_fees_and_payout_type
Revises: e3_add_pawapay_deposit_fields
Create Date: 2026-02-15 04:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1_add_platform_fees_and_payout_type'
down_revision = 'e3_add_pawapay_deposit_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create platform_fees table
    op.create_table(
        'platform_fees',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('deposit_id', sa.String(64), nullable=True),
        sa.Column('order_id', sa.String(64), nullable=True),
        sa.Column('currency', sa.String(8), nullable=False, server_default='ZMW'),
        sa.Column('amount_minor', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('meta', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('deposit_id', name='uq_platform_fee_deposit')
    )
    op.create_index(op.f('ix_platform_fees_deposit_id'), 'platform_fees', ['deposit_id'], unique=False)
    op.create_index(op.f('ix_platform_fees_order_id'), 'platform_fees', ['order_id'], unique=False)

    # Add payout_type column to pawapay_payouts with a safe server default and make non-nullable
    op.add_column('pawapay_payouts', sa.Column('payout_type', sa.String(length=32), nullable=False, server_default='msme'))


def downgrade() -> None:
    # Drop payout_type column
    op.drop_column('pawapay_payouts', 'payout_type')

    # Drop platform_fees table
    op.drop_index(op.f('ix_platform_fees_order_id'), table_name='platform_fees')
    op.drop_index(op.f('ix_platform_fees_deposit_id'), table_name='platform_fees')
    op.drop_table('platform_fees')
