"""add time robustness to agent iterations

Revision ID: 20260426_000025
Revises: 20260426_000024
Create Date: 2026-04-26 00:00:25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260426_000025"
down_revision = "20260426_000024"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "agent_iterations",
        sa.Column(
            "time_robustness",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("agent_iterations", "time_robustness")
