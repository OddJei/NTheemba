"""create audit_logs table

Revision ID: 0001_create_audit_logs
Revises: 
Create Date: 2025-11-05 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_create_audit_logs'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create schema if it doesn't exist and create table inside audit_service schema
    op.execute("CREATE SCHEMA IF NOT EXISTS audit_service")

    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('service', sa.String(length=128), nullable=False),
        sa.Column('event_type', sa.String(length=128), nullable=False),
        sa.Column('actor_id', sa.String(length=36), nullable=True),
        sa.Column('entity_type', sa.String(length=128), nullable=True),
        sa.Column('entity_id', sa.String(length=36), nullable=True),
        sa.Column('severity', sa.String(length=16), nullable=False, server_default='info'),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('checksum', sa.String(length=128), nullable=True),
        sa.Column('archived', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        schema='audit_service'
    )

    op.create_index('idx_audit_occurred_at', 'audit_logs', ['occurred_at'], schema='audit_service')
    op.create_index('idx_audit_service_event', 'audit_logs', ['service', 'event_type'], schema='audit_service')
    op.create_index('idx_audit_entity', 'audit_logs', ['entity_type', 'entity_id'], schema='audit_service')


def downgrade():
    op.drop_index('idx_audit_entity', table_name='audit_logs', schema='audit_service')
    op.drop_index('idx_audit_service_event', table_name='audit_logs', schema='audit_service')
    op.drop_index('idx_audit_occurred_at', table_name='audit_logs', schema='audit_service')
    op.drop_table('audit_logs', schema='audit_service')
