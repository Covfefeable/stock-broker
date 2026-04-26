"""add min add position interval to agent tasks

Revision ID: 20260426_000026
Revises: 20260426_000025
Create Date: 2026-04-26 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260426_000026"
down_revision = "20260426_000025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_tasks",
        sa.Column("min_add_position_interval", sa.Integer(), nullable=False, server_default="3"),
    )
    op.alter_column("agent_tasks", "min_add_position_interval", server_default=None)


def downgrade() -> None:
    op.drop_column("agent_tasks", "min_add_position_interval")
