"""add escalation reason to support ticket and enum values

Revision ID: 5c38d12e9f01
Revises: a1b2c3d4e5f6
Create Date: 2026-10-14 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5c38d12e9f01'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
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

    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "support_ticket" in tables:
        columns = [c["name"] for c in inspector.get_columns("support_ticket")]
        if "escalation_reason" not in columns:
            op.add_column("support_ticket", sa.Column("escalation_reason", sa.Text(), nullable=True))
    else:
        # Fallback if table doesn't exist yet
        op.create_table(
            'support_ticket',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('ticket_number', sa.String(length=50), nullable=False),
            sa.Column('subject', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('category', sa.String(length=50), server_default='other', nullable=False),
            sa.Column('priority', sa.String(length=20), server_default='MEDIUM', nullable=False),
            sa.Column('status', sa.String(length=30), server_default='open', nullable=False),
            sa.Column('escalation_reason', sa.Text(), nullable=True),
            sa.Column('reporter_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('assigned_to', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['assigned_to'], ['user_account.account_id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['reporter_id'], ['user_account.account_id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_support_ticket_ticket_number'), 'support_ticket', ['ticket_number'], unique=True)
        op.create_index(op.f('ix_support_ticket_status'), 'support_ticket', ['status'], unique=False)
        op.create_index(op.f('ix_support_ticket_reporter_id'), 'support_ticket', ['reporter_id'], unique=False)
        op.create_index(op.f('ix_support_ticket_assigned_to'), 'support_ticket', ['assigned_to'], unique=False)

    if "ticket_activity" not in tables:
        op.create_table(
            'ticket_activity',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('ticket_id', sa.Integer(), nullable=False),
            sa.Column('actor_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('action', sa.String(length=50), nullable=False),
            sa.Column('note', sa.Text(), nullable=True),
            sa.Column('old_status', sa.String(length=50), nullable=True),
            sa.Column('new_status', sa.String(length=50), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.ForeignKeyConstraint(['actor_id'], ['user_account.account_id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['ticket_id'], ['support_ticket.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_ticket_activity_ticket_id'), 'ticket_activity', ['ticket_id'], unique=False)
        op.create_index(op.f('ix_ticket_activity_actor_id'), 'ticket_activity', ['actor_id'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    if "support_ticket" in tables:
        columns = [c["name"] for c in inspector.get_columns("support_ticket")]
        if "escalation_reason" in columns:
            op.drop_column("support_ticket", "escalation_reason")
