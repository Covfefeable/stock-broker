"""add ai model to agent tasks

Revision ID: 20260424_000018
Revises: 20260424_000017
Create Date: 2026-04-24 20:05:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260424_000018"
down_revision = "20260424_000017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_tasks", sa.Column("ai_model_name", sa.String(length=255), nullable=True))
    op.add_column("agent_tasks", sa.Column("ai_model_config", sa.JSON(), nullable=True))
    op.execute("UPDATE agent_tasks SET ai_model_name = '未配置模型' WHERE ai_model_name IS NULL")
    op.execute("UPDATE agent_tasks SET ai_model_config = '{}' WHERE ai_model_config IS NULL")
    op.alter_column("agent_tasks", "ai_model_name", nullable=False)
    op.alter_column("agent_tasks", "ai_model_config", nullable=False)


def downgrade() -> None:
    op.drop_column("agent_tasks", "ai_model_config")
    op.drop_column("agent_tasks", "ai_model_name")
