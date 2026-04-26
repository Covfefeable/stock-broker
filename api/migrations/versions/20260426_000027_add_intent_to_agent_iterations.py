"""add intent to agent iterations

Revision ID: 20260426_000027
Revises: 20260426_000026
Create Date: 2026-04-26 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260426_000027"
down_revision = "20260426_000026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_iterations", sa.Column("intent", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("agent_iterations", "intent")
