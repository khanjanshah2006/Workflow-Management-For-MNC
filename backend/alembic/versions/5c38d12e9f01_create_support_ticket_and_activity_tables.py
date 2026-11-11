"""create support ticket and activity tables

Revision ID: 5c38d12e9f01
Revises: 4b29f01e7a32
Create Date: 2026-10-14 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5c38d12e9f01'
down_revision: Union[str, Sequence[str], None] = '4b29f01e7a32'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # In PostgreSQL, ALTER TYPE ... ADD VALUE cannot run inside an ongoing transaction block
        # when subsequent statements use or reference the enum. Using autocommit_block ensures safe execution.
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE user_type_enum ADD VALUE IF NOT EXISTS 'IT_SUPPORT'")
            op.execute("ALTER TYPE user_type_enum ADD VALUE IF NOT EXISTS 'SYSTEM_ADMIN'")

    op.create_table(
        'support_ticket',
        sa.Column('ticket_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ticket_number', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('priority', sa.String(length=50), server_default='MEDIUM', nullable=False),
        sa.Column('status', sa.String(length=50), server_default='open', nullable=False),
        sa.Column('escalation_reason', sa.Text(), nullable=True),
        sa.Column('reporter_id', sa.Integer(), nullable=True),
        sa.Column('assigned_to', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['assigned_to'], ['employee.emp_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reporter_id'], ['employee.emp_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('ticket_id')
    )
    op.create_index(op.f('ix_support_ticket_ticket_number'), 'support_ticket', ['ticket_number'], unique=True)
    op.create_index(op.f('ix_support_ticket_status'), 'support_ticket', ['status'], unique=False)
    op.create_index(op.f('ix_support_ticket_reporter_id'), 'support_ticket', ['reporter_id'], unique=False)
    op.create_index(op.f('ix_support_ticket_assigned_to'), 'support_ticket', ['assigned_to'], unique=False)

    op.create_table(
        'ticket_activity',
        sa.Column('activity_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ticket_id', sa.Integer(), nullable=False),
        sa.Column('activity_type', sa.String(length=50), nullable=False),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('actor_account_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['actor_account_id'], ['user_account.account_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['ticket_id'], ['support_ticket.ticket_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('activity_id')
    )
    op.create_index(op.f('ix_ticket_activity_ticket_id'), 'ticket_activity', ['ticket_id'], unique=False)
    op.create_index(op.f('ix_ticket_activity_actor_account_id'), 'ticket_activity', ['actor_account_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_ticket_activity_actor_account_id'), table_name='ticket_activity')
    op.drop_index(op.f('ix_ticket_activity_ticket_id'), table_name='ticket_activity')
    op.drop_table('ticket_activity')
    op.drop_index(op.f('ix_support_ticket_assigned_to'), table_name='support_ticket')
    op.drop_index(op.f('ix_support_ticket_reporter_id'), table_name='support_ticket')
    op.drop_index(op.f('ix_support_ticket_status'), table_name='support_ticket')
    op.drop_index(op.f('ix_support_ticket_ticket_number'), table_name='support_ticket')
    op.drop_table('support_ticket')
    # Note: PostgreSQL does not provide a native 'ALTER TYPE ... DROP VALUE' syntax to remove enum values.
    # Leaving unused enum values in place is safe and standard practice (matching 4b29f01e7a32).

