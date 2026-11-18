"""create system_backup_log table

Revision ID: 6d49e23f0a12
Revises: 5c38d12e9f01
Create Date: 2026-10-14 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '6d49e23f0a12'
down_revision: Union[str, Sequence[str], None] = '5c38d12e9f01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'system_backup_log',
        sa.Column('backup_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('triggered_by_account_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('backup_type', sa.String(length=50), server_default='ON_DEMAND', nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('status', sa.String(length=50), server_default='COMPLETED', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['triggered_by_account_id'], ['user_account.account_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('backup_id')
    )
    op.create_index(op.f('ix_system_backup_log_triggered_by_account_id'), 'system_backup_log', ['triggered_by_account_id'], unique=False)
    op.create_index(op.f('ix_system_backup_log_status'), 'system_backup_log', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_system_backup_log_status'), table_name='system_backup_log')
    op.drop_index(op.f('ix_system_backup_log_triggered_by_account_id'), table_name='system_backup_log')
    op.drop_table('system_backup_log')

