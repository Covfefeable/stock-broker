"""add equity preview to agent iterations

Revision ID: 20260430_000033
Revises: 20260428_000032
Create Date: 2026-04-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260430_000033"
down_revision = "20260428_000032"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "agent_iterations",
        sa.Column("equity_preview", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade():
    op.drop_column("agent_iterations", "equity_preview")
