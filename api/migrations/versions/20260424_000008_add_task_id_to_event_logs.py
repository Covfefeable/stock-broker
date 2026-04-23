"""add task_id to event_logs

Revision ID: 20260424_000008
Revises: 20260424_000007
Create Date: 2026-04-24 00:08:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260424_000008"
down_revision = "20260424_000007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("event_logs", sa.Column("task_id", sa.String(length=128), nullable=True))
    op.create_index(op.f("ix_event_logs_task_id"), "event_logs", ["task_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_event_logs_task_id"), table_name="event_logs")
    op.drop_column("event_logs", "task_id")
