"""create agent tasks and iterations

Revision ID: 20260424_000017
Revises: 20260424_000016
Create Date: 2026-04-24 19:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260424_000017"
down_revision = "20260424_000016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("country_code", sa.String(length=8), nullable=False),
        sa.Column("asset_type", sa.String(length=16), nullable=False),
        sa.Column("asset_identifier", sa.String(length=64), nullable=False),
        sa.Column("asset_name", sa.String(length=255), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("max_iterations", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("current_iteration", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("target_annual_return", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("max_drawdown_limit", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("min_sharpe", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("initial_capital", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("position_size", sa.Numeric(precision=8, scale=4), nullable=False),
        sa.Column("stop_loss", sa.Numeric(precision=8, scale=4), nullable=False),
        sa.Column("take_profit", sa.Numeric(precision=8, scale=4), nullable=False),
        sa.Column("max_holding_days", sa.Integer(), nullable=False),
        sa.Column("backtest_start_date", sa.Date(), nullable=False),
        sa.Column("backtest_end_date", sa.Date(), nullable=False),
        sa.Column("best_annual_return", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("best_sharpe", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("best_strategy_config", sa.JSON(), nullable=True),
        sa.Column("best_summary", sa.Text(), nullable=True),
        sa.Column("celery_task_id", sa.String(length=128), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_tasks_user_id"), "agent_tasks", ["user_id"], unique=False)
    op.create_index(op.f("ix_agent_tasks_country_code"), "agent_tasks", ["country_code"], unique=False)
    op.create_index(op.f("ix_agent_tasks_asset_type"), "agent_tasks", ["asset_type"], unique=False)
    op.create_index(op.f("ix_agent_tasks_status"), "agent_tasks", ["status"], unique=False)
    op.create_index(op.f("ix_agent_tasks_celery_task_id"), "agent_tasks", ["celery_task_id"], unique=False)

    op.create_table(
        "agent_iterations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("iteration_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="success"),
        sa.Column("annual_return", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("max_drawdown", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("sharpe", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("strategy_config", sa.JSON(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["agent_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_iterations_task_id"), "agent_iterations", ["task_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_iterations_task_id"), table_name="agent_iterations")
    op.drop_table("agent_iterations")
    op.drop_index(op.f("ix_agent_tasks_celery_task_id"), table_name="agent_tasks")
    op.drop_index(op.f("ix_agent_tasks_status"), table_name="agent_tasks")
    op.drop_index(op.f("ix_agent_tasks_asset_type"), table_name="agent_tasks")
    op.drop_index(op.f("ix_agent_tasks_country_code"), table_name="agent_tasks")
    op.drop_index(op.f("ix_agent_tasks_user_id"), table_name="agent_tasks")
    op.drop_table("agent_tasks")
