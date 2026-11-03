"""support: add support_ticket and ticket_activity tables

Revision ID: 3a105c6d7e89
Revises: 2e204e5a4c37
Create Date: 2026-11-03 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3a105c6d7e89"
down_revision: Union[str, Sequence[str], None] = "2e204e5a4c37"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create support_ticket table
    op.create_table(
        "support_ticket",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticket_number", sa.String(length=50), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False, server_default="other"),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default="MEDIUM"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="open"),
        sa.Column("reporter_id", sa.UUID(), nullable=False),
        sa.Column("assigned_to", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["reporter_id"], ["user_account.account_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_to"], ["user_account.account_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_support_ticket_ticket_number"), "support_ticket", ["ticket_number"], unique=True)
    op.create_index(op.f("ix_support_ticket_status"), "support_ticket", ["status"], unique=False)
    op.create_index(op.f("ix_support_ticket_category"), "support_ticket", ["category"], unique=False)
    op.create_index(op.f("ix_support_ticket_reporter_id"), "support_ticket", ["reporter_id"], unique=False)
    op.create_index(op.f("ix_support_ticket_assigned_to"), "support_ticket", ["assigned_to"], unique=False)

    # 2. Create ticket_activity table
    op.create_table(
        "ticket_activity",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("old_status", sa.String(length=50), nullable=True),
        sa.Column("new_status", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["support_ticket.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["user_account.account_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ticket_activity_ticket_id"), "ticket_activity", ["ticket_id"], unique=False)
    op.create_index(op.f("ix_ticket_activity_actor_id"), "ticket_activity", ["actor_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ticket_activity_actor_id"), table_name="ticket_activity")
    op.drop_index(op.f("ix_ticket_activity_ticket_id"), table_name="ticket_activity")
    op.drop_table("ticket_activity")

    op.drop_index(op.f("ix_support_ticket_assigned_to"), table_name="support_ticket")
    op.drop_index(op.f("ix_support_ticket_reporter_id"), table_name="support_ticket")
    op.drop_index(op.f("ix_support_ticket_category"), table_name="support_ticket")
    op.drop_index(op.f("ix_support_ticket_status"), table_name="support_ticket")
    op.drop_index(op.f("ix_support_ticket_ticket_number"), table_name="support_ticket")
    op.drop_table("support_ticket")
