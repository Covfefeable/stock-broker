"""add strategy config to strategies

Revision ID: 20260424_000016
Revises: 20260424_000015
Create Date: 2026-04-24 18:20:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260424_000016"
down_revision = "20260424_000015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("strategies", sa.Column("strategy_config", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("strategies", "strategy_config")
