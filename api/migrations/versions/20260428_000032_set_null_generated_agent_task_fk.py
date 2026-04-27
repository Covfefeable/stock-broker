"""set null generated agent task on delete

Revision ID: 20260428_000032
Revises: 20260428_000031
Create Date: 2026-04-28
"""

from alembic import op


revision = "20260428_000032"
down_revision = "20260428_000031"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        "scheduled_plan_runs_generated_agent_task_id_fkey",
        "scheduled_plan_runs",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "scheduled_plan_runs_generated_agent_task_id_fkey",
        "scheduled_plan_runs",
        "agent_tasks",
        ["generated_agent_task_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint(
        "scheduled_plan_runs_generated_agent_task_id_fkey",
        "scheduled_plan_runs",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "scheduled_plan_runs_generated_agent_task_id_fkey",
        "scheduled_plan_runs",
        "agent_tasks",
        ["generated_agent_task_id"],
        ["id"],
    )
