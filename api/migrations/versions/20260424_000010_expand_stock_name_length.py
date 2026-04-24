"""expand stock name length

Revision ID: 20260424_000010
Revises: 20260424_000009
Create Date: 2026-04-24 08:58:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260424_000010"
down_revision = "20260424_000009"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "stocks",
        "name",
        existing_type=sa.String(length=160),
        type_=sa.String(length=512),
        existing_nullable=False,
    )


def downgrade():
    op.alter_column(
        "stocks",
        "name",
        existing_type=sa.String(length=512),
        type_=sa.String(length=160),
        existing_nullable=False,
    )
