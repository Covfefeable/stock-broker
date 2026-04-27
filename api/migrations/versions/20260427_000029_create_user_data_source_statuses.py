"""create user data source statuses

Revision ID: 20260427_000029
Revises: 20260427_000028
Create Date: 2026-04-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260427_000029"
down_revision = "20260427_000028"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "settings",
        sa.Column(
            "canghai_token_check_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.alter_column("settings", "canghai_token_check_enabled", server_default=None)

    op.create_table(
        "user_data_source_statuses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("source_key", sa.String(length=64), nullable=False),
        sa.Column("source_name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("token_status", sa.String(length=32), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("message", sa.String(length=255), nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "source_key", name="uq_user_data_source_status"),
    )
    op.create_index(
        op.f("ix_user_data_source_statuses_source_key"),
        "user_data_source_statuses",
        ["source_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_data_source_statuses_user_id"),
        "user_data_source_statuses",
        ["user_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_user_data_source_statuses_user_id"), table_name="user_data_source_statuses")
    op.drop_index(op.f("ix_user_data_source_statuses_source_key"), table_name="user_data_source_statuses")
    op.drop_table("user_data_source_statuses")
    op.drop_column("settings", "canghai_token_check_enabled")
