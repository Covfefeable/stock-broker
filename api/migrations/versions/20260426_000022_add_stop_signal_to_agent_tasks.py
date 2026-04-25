"""add stop signal to agent tasks

Revision ID: 20260426_000022
Revises: 20260426_000021
Create Date: 2026-04-26 02:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260426_000022"
down_revision = "20260426_000021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_tasks",
        sa.Column("stop_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("agent_tasks", sa.Column("stop_requested_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_agent_tasks_stop_requested"), "agent_tasks", ["stop_requested"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_tasks_stop_requested"), table_name="agent_tasks")
    op.drop_column("agent_tasks", "stop_requested_at")
    op.drop_column("agent_tasks", "stop_requested")
