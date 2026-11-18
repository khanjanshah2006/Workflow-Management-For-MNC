"""Allow failed backup rows and use an in-progress initial status.

Revision ID: 7e2a91c4b6d8
Revises: 6d49e23f0a12
"""
from alembic import op
import sqlalchemy as sa

revision = "7e2a91c4b6d8"
down_revision = "6d49e23f0a12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "system_backup_log",
        "file_path",
        existing_type=sa.String(length=500),
        nullable=True,
    )
    op.alter_column(
        "system_backup_log",
        "status",
        existing_type=sa.String(length=50),
        existing_nullable=False,
        server_default="IN_PROGRESS",
    )
    op.create_check_constraint(
        "ck_system_backup_log_status",
        "system_backup_log",
        "status IN ('IN_PROGRESS', 'COMPLETED', 'FAILED')",
    )


def downgrade() -> None:
    # Failed rows may have NULL paths; make them explicit before restoring NOT NULL.
    op.execute(
        "UPDATE system_backup_log SET file_path = '' WHERE file_path IS NULL"
    )
    op.alter_column(
        "system_backup_log",
        "file_path",
        existing_type=sa.String(length=500),
        nullable=False,
    )
    op.drop_constraint("ck_system_backup_log_status", "system_backup_log", type_="check")
    op.alter_column(
        "system_backup_log",
        "status",
        existing_type=sa.String(length=50),
        existing_nullable=False,
        server_default="COMPLETED",
    )
