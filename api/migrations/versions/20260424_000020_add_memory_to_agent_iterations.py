"""add memory to agent iterations

Revision ID: 20260424_000020
Revises: 20260424_000019
Create Date: 2026-04-24 20:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260424_000020"
down_revision = "20260424_000019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_iterations", sa.Column("memory", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("agent_iterations", "memory")
