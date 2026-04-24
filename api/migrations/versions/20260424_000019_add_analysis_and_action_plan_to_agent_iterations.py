"""add analysis and action plan to agent iterations

Revision ID: 20260424_000019
Revises: 20260424_000018
Create Date: 2026-04-24 19:55:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260424_000019"
down_revision = "20260424_000018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_iterations", sa.Column("analysis", sa.Text(), nullable=True))
    op.add_column("agent_iterations", sa.Column("action_plan", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("agent_iterations", "action_plan")
    op.drop_column("agent_iterations", "analysis")
