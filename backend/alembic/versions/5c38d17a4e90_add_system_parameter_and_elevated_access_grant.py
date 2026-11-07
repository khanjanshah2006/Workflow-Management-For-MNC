"""add system_parameter and elevated_access_grant

Revision ID: 5c38d17a4e90
Revises: 4b29f01e7a32
Create Date: 2026-11-03 11:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = '5c38d17a4e90'
down_revision: Union[str, Sequence[str], None] = '4b29f01e7a32'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create system_parameter table
    system_param_table = op.create_table(
        'system_parameter',
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.String(length=500), nullable=False),
        sa.Column('value_type', sa.String(length=20), server_default='string', nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_by', UUID(as_uuid=True), sa.ForeignKey('user_account.account_id', ondelete='SET NULL'), nullable=True),
        sa.PrimaryKeyConstraint('key')
    )

    # 2. Seed initial default system parameters
    op.bulk_insert(
        system_param_table,
        [
            {
                'key': 'session_timeout_minutes',
                'value': '60',
                'value_type': 'integer',
                'description': 'User session idle timeout in minutes',
            },
            {
                'key': 'max_upload_size_mb',
                'value': '25',
                'value_type': 'integer',
                'description': 'Maximum file attachment size in megabytes',
            },
            {
                'key': 'allow_client_signup',
                'value': 'false',
                'value_type': 'boolean',
                'description': 'Whether public clients can register accounts',
            },
        ]
    )

    # 3. Create elevated_access_grant table
    op.create_table(
        'elevated_access_grant',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('user_account.account_id', ondelete='CASCADE'), nullable=False),
        sa.Column('granted_role', sa.String(length=50), nullable=False),
        sa.Column('granted_by', UUID(as_uuid=True), sa.ForeignKey('user_account.account_id', ondelete='SET NULL'), nullable=False),
        sa.Column('granted_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_elevated_access_grant_user_id', 'elevated_access_grant', ['user_id'])
    op.create_index('ix_elevated_access_grant_expires_at', 'elevated_access_grant', ['expires_at'])


def downgrade() -> None:
    op.drop_index('ix_elevated_access_grant_expires_at', table_name='elevated_access_grant')
    op.drop_index('ix_elevated_access_grant_user_id', table_name='elevated_access_grant')
    op.drop_table('elevated_access_grant')
    op.drop_table('system_parameter')
