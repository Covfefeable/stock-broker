"""create strategy evaluations

Revision ID: 20260426_000023
Revises: 20260426_000022
Create Date: 2026-04-26 05:20:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260426_000023"
down_revision = "20260426_000022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "strategy_evaluations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("strategy_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("score", sa.Numeric(10, 2), nullable=True),
        sa.Column("conclusion", sa.String(length=32), nullable=True),
        sa.Column("generality_conclusion", sa.String(length=64), nullable=True),
        sa.Column("stability_conclusion", sa.String(length=64), nullable=True),
        sa.Column("risk_conclusion", sa.String(length=64), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("celery_task_id", sa.String(length=128), nullable=True),
        sa.Column("strategy_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("report", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "strategy_id", name="uq_strategy_evaluations_user_strategy"),
    )
    op.create_index(op.f("ix_strategy_evaluations_celery_task_id"), "strategy_evaluations", ["celery_task_id"], unique=False)
    op.create_index(op.f("ix_strategy_evaluations_status"), "strategy_evaluations", ["status"], unique=False)
    op.create_index(op.f("ix_strategy_evaluations_strategy_id"), "strategy_evaluations", ["strategy_id"], unique=False)
    op.create_index(op.f("ix_strategy_evaluations_user_id"), "strategy_evaluations", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_strategy_evaluations_user_id"), table_name="strategy_evaluations")
    op.drop_index(op.f("ix_strategy_evaluations_strategy_id"), table_name="strategy_evaluations")
    op.drop_index(op.f("ix_strategy_evaluations_status"), table_name="strategy_evaluations")
    op.drop_index(op.f("ix_strategy_evaluations_celery_task_id"), table_name="strategy_evaluations")
    op.drop_table("strategy_evaluations")
