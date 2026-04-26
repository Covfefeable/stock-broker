"""add performance score weights to settings

Revision ID: 20260426_000024
Revises: 20260426_000023
Create Date: 2026-04-26 00:00:24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260426_000024"
down_revision = "20260426_000023"
branch_labels = None
depends_on = None


DEFAULT_WEIGHTS = '{"annualReturn": 0.7, "sharpe": 5, "maxDrawdown": 0.2}'


def upgrade():
    op.add_column(
        "settings",
        sa.Column(
            "performance_score_weights",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text(f"'{DEFAULT_WEIGHTS}'::jsonb"),
        ),
    )
    op.execute(
        "UPDATE settings SET performance_score_weights = "
        f"'{DEFAULT_WEIGHTS}'::jsonb "
        "WHERE performance_score_weights IS NULL"
    )
    op.alter_column("settings", "performance_score_weights", nullable=False, server_default=None)


def downgrade():
    op.drop_column("settings", "performance_score_weights")
