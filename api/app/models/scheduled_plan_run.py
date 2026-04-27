from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import JSONB

from app.extensions import db


class ScheduledPlanRun(db.Model):
    __tablename__ = "scheduled_plan_runs"

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("scheduled_plans.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    agent_task_id = db.Column(db.Integer, db.ForeignKey("agent_tasks.id"), nullable=False, index=True)
    generated_agent_task_id = db.Column(
        db.Integer,
        db.ForeignKey("agent_tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status = db.Column(db.String(32), nullable=False, default="pending", index=True)
    trigger_type = db.Column(db.String(32), nullable=False, default="schedule")
    saved_strategy_ids = db.Column(JSONB().with_variant(db.JSON(), "sqlite"), nullable=False, default=list)
    error_message = db.Column(db.String(512), nullable=True)
    started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    finished_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    plan = db.relationship("ScheduledPlan", back_populates="runs")
    user = db.relationship("User")
    source_agent_task = db.relationship("AgentTask", foreign_keys=[agent_task_id])
    generated_agent_task = db.relationship("AgentTask", foreign_keys=[generated_agent_task_id])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "planId": self.plan_id,
            "agentTaskId": self.agent_task_id,
            "agentTaskName": self.source_agent_task.name if self.source_agent_task else None,
            "generatedAgentTaskId": self.generated_agent_task_id,
            "generatedAgentTaskName": self.generated_agent_task.name if self.generated_agent_task else None,
            "status": self.status,
            "triggerType": self.trigger_type,
            "savedStrategyIds": self.saved_strategy_ids or [],
            "errorMessage": self.error_message,
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "finishedAt": self.finished_at.isoformat() if self.finished_at else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
