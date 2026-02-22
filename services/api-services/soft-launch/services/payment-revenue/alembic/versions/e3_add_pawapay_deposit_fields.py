"""Add platform fee and bookkeeping fields to pawapay_deposits

Revision ID: e3_add_pawapay_deposit_fields
Revises: d1
Create Date: 2026-02-15 03:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e3_add_pawapay_deposit_fields'
down_revision = 'd1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add bookkeeping columns used by application code.
    op.add_column('pawapay_deposits', sa.Column('platform_fee_minor', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('pawapay_deposits', sa.Column('fee_bps', sa.Integer(), nullable=True))
    op.add_column('pawapay_deposits', sa.Column('payment_type', sa.String(length=32), nullable=True))
    op.add_column('pawapay_deposits', sa.Column('msme_net_minor', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('pawapay_deposits', sa.Column('provider_transaction_id', sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column('pawapay_deposits', 'provider_transaction_id')
    op.drop_column('pawapay_deposits', 'msme_net_minor')
    op.drop_column('pawapay_deposits', 'payment_type')
    op.drop_column('pawapay_deposits', 'fee_bps')
    op.drop_column('pawapay_deposits', 'platform_fee_minor')
