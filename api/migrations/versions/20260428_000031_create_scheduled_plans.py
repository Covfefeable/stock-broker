"""create scheduled plans

Revision ID: 20260428_000031
Revises: 20260427_000030
Create Date: 2026-04-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260428_000031"
down_revision = "20260427_000030"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "scheduled_plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("agent_task_id", sa.Integer(), nullable=False),
        sa.Column("frequency_type", sa.String(length=16), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Asia/Shanghai"),
        sa.Column("time_of_day", sa.Time(), nullable=True),
        sa.Column("minute_of_hour", sa.Integer(), nullable=True),
        sa.Column("month_days", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("use_last_day", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("weekdays", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("save_top_n", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("score_threshold_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("score_threshold", sa.Numeric(10, 2), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="enabled"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_message", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_task_id"], ["agent_tasks.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_scheduled_plans_agent_task_id"), "scheduled_plans", ["agent_task_id"], unique=False)
    op.create_index(op.f("ix_scheduled_plans_frequency_type"), "scheduled_plans", ["frequency_type"], unique=False)
    op.create_index(op.f("ix_scheduled_plans_next_run_at"), "scheduled_plans", ["next_run_at"], unique=False)
    op.create_index(op.f("ix_scheduled_plans_status"), "scheduled_plans", ["status"], unique=False)
    op.create_index(op.f("ix_scheduled_plans_user_id"), "scheduled_plans", ["user_id"], unique=False)

    op.create_table(
        "scheduled_plan_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("agent_task_id", sa.Integer(), nullable=False),
        sa.Column("generated_agent_task_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("trigger_type", sa.String(length=32), nullable=False, server_default="schedule"),
        sa.Column("saved_strategy_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("error_message", sa.String(length=512), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_task_id"], ["agent_tasks.id"]),
        sa.ForeignKeyConstraint(["generated_agent_task_id"], ["agent_tasks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["plan_id"], ["scheduled_plans.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_scheduled_plan_runs_agent_task_id"), "scheduled_plan_runs", ["agent_task_id"], unique=False)
    op.create_index(
        op.f("ix_scheduled_plan_runs_generated_agent_task_id"),
        "scheduled_plan_runs",
        ["generated_agent_task_id"],
        unique=False,
    )
    op.create_index(op.f("ix_scheduled_plan_runs_plan_id"), "scheduled_plan_runs", ["plan_id"], unique=False)
    op.create_index(op.f("ix_scheduled_plan_runs_status"), "scheduled_plan_runs", ["status"], unique=False)
    op.create_index(op.f("ix_scheduled_plan_runs_user_id"), "scheduled_plan_runs", ["user_id"], unique=False)

    for table in ("scheduled_plans", "scheduled_plan_runs"):
        op.alter_column(table, "created_at", server_default=None)
        op.alter_column(table, "updated_at", server_default=None)


def downgrade():
    op.drop_index(op.f("ix_scheduled_plan_runs_user_id"), table_name="scheduled_plan_runs")
    op.drop_index(op.f("ix_scheduled_plan_runs_status"), table_name="scheduled_plan_runs")
    op.drop_index(op.f("ix_scheduled_plan_runs_plan_id"), table_name="scheduled_plan_runs")
    op.drop_index(op.f("ix_scheduled_plan_runs_generated_agent_task_id"), table_name="scheduled_plan_runs")
    op.drop_index(op.f("ix_scheduled_plan_runs_agent_task_id"), table_name="scheduled_plan_runs")
    op.drop_table("scheduled_plan_runs")
    op.drop_index(op.f("ix_scheduled_plans_user_id"), table_name="scheduled_plans")
    op.drop_index(op.f("ix_scheduled_plans_status"), table_name="scheduled_plans")
    op.drop_index(op.f("ix_scheduled_plans_next_run_at"), table_name="scheduled_plans")
    op.drop_index(op.f("ix_scheduled_plans_frequency_type"), table_name="scheduled_plans")
    op.drop_index(op.f("ix_scheduled_plans_agent_task_id"), table_name="scheduled_plans")
    op.drop_table("scheduled_plans")
