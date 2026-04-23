"""create settings

Revision ID: 20260424_000002
Revises: 20260424_000001
Create Date: 2026-04-24 00:00:02

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260424_000002"
down_revision = "20260424_000001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("canghai_api_key", sa.Text(), nullable=True),
        sa.Column("ai_models", sa.JSON(), nullable=False),
        sa.Column("notification_data_sync", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notification_agent_goal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notification_backtest", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("keep_signed_in", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(op.f("ix_settings_user_id"), "settings", ["user_id"], unique=True)


def downgrade():
    op.drop_index(op.f("ix_settings_user_id"), table_name="settings")
    op.drop_table("settings")
