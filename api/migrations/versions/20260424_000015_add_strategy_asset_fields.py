"""add strategy asset fields

Revision ID: 20260424_000015
Revises: 20260424_000014
Create Date: 2026-04-24 17:45:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260424_000015"
down_revision = "20260424_000014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("strategies", sa.Column("asset_type", sa.String(length=16), nullable=True))
    op.add_column("strategies", sa.Column("asset_identifier", sa.String(length=64), nullable=True))
    op.add_column("strategies", sa.Column("asset_name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("strategies", "asset_name")
    op.drop_column("strategies", "asset_identifier")
    op.drop_column("strategies", "asset_type")
