"""add stable author details to task comments

Revision ID: 9c0d1e2f3a4b
Revises: 8b9c0d1e2f3a
Create Date: 2026-11-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9c0d1e2f3a4b"
# The existing repository has parallel migration heads. Join them here so
# `alembic upgrade head` remains unambiguous after this feature is applied.
down_revision: Union[str, Sequence[str], None] = (
    "5c38d17a4e90",
    "5c71a8e2b109",
    "5c83b12a9e40",
    "6d7e9f0a1b2c",
    "7a8b9c0d1e2f",
    "8b9c0d1e2f3a",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # task_comment and its core fields were introduced in the initial schema.
    # Snapshots let PM/Admin comments retain an author badge without an employee FK.
    op.add_column("task_comment", sa.Column("author_name", sa.String(length=150), nullable=True))
    op.add_column("task_comment", sa.Column("author_role", sa.String(length=30), nullable=True))


def downgrade() -> None:
    op.drop_column("task_comment", "author_role")
    op.drop_column("task_comment", "author_name")
