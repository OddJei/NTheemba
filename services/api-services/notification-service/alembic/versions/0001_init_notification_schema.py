"""initial notification schema

Revision ID: 0001_init_notification_schema
Revises: 
Create Date: 2025-11-08
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_init_notification_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # create schema if not exists
    op.execute("CREATE SCHEMA IF NOT EXISTS notification_service")

    # notifications table
    op.create_table(
        'notifications',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('business_id', sa.String(length=36), nullable=True),
        sa.Column('channel', sa.String(length=32), nullable=False),
        sa.Column('template', sa.Text(), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        schema='notification_service'
    )

    # templates table
    op.create_table(
        'templates',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False, unique=True),
        sa.Column('channel', sa.String(length=32), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        schema='notification_service'
    )

    # user_preferences table
    op.create_table(
        'user_preferences',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('user_id', sa.String(length=36), nullable=False, unique=True),
        sa.Column('preferred_channel', sa.String(length=32), nullable=True),
        sa.Column('opt_in', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        schema='notification_service'
    )


def downgrade():
    op.drop_table('user_preferences', schema='notification_service')
    op.drop_table('templates', schema='notification_service')
    op.drop_table('notifications', schema='notification_service')
    op.execute("DROP SCHEMA IF EXISTS notification_service")
