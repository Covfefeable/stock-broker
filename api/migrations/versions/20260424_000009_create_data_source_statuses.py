"""create data source statuses

Revision ID: 20260424_000009
Revises: 20260424_000008
Create Date: 2026-04-24 08:45:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260424_000009"
down_revision = "20260424_000008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "data_source_statuses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_key", sa.String(length=64), nullable=False),
        sa.Column("source_name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("message", sa.String(length=255), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_data_source_statuses_source_key"),
        "data_source_statuses",
        ["source_key"],
        unique=True,
    )


def downgrade():
    op.drop_index(op.f("ix_data_source_statuses_source_key"), table_name="data_source_statuses")
    op.drop_table("data_source_statuses")
