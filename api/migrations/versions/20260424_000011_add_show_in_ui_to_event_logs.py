"""add show_in_ui to event_logs

Revision ID: 20260424_000011
Revises: 20260424_000010
Create Date: 2026-04-24 09:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260424_000011"
down_revision = "20260424_000010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "event_logs",
        sa.Column("show_in_ui", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index(op.f("ix_event_logs_show_in_ui"), "event_logs", ["show_in_ui"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_event_logs_show_in_ui"), table_name="event_logs")
    op.drop_column("event_logs", "show_in_ui")
