"""create strategies

Revision ID: 20260424_000014
Revises: 20260424_000013
Create Date: 2026-04-24 17:10:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260424_000014"
down_revision = "20260424_000013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "strategies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="人工创建"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="草稿"),
        sa.Column("country_region", sa.String(length=64), nullable=False),
        sa.Column("annual_return", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("max_drawdown", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_strategies_user_id"), "strategies", ["user_id"], unique=False)
    op.create_index(op.f("ix_strategies_status"), "strategies", ["status"], unique=False)
    op.create_index(op.f("ix_strategies_country_region"), "strategies", ["country_region"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_strategies_country_region"), table_name="strategies")
    op.drop_index(op.f("ix_strategies_status"), table_name="strategies")
    op.drop_index(op.f("ix_strategies_user_id"), table_name="strategies")
    op.drop_table("strategies")
