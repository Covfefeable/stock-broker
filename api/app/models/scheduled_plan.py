from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import JSONB

from app.extensions import db


class ScheduledPlan(db.Model):
    __tablename__ = "scheduled_plans"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    agent_task_id = db.Column(db.Integer, db.ForeignKey("agent_tasks.id"), nullable=False, index=True)
    frequency_type = db.Column(db.String(16), nullable=False, index=True)
    timezone = db.Column(db.String(64), nullable=False, default="Asia/Shanghai")
    time_of_day = db.Column(db.Time(), nullable=True)
    minute_of_hour = db.Column(db.Integer, nullable=True)
    month_days = db.Column(JSONB().with_variant(db.JSON(), "sqlite"), nullable=False, default=list)
    use_last_day = db.Column(db.Boolean, nullable=False, default=False)
    weekdays = db.Column(JSONB().with_variant(db.JSON(), "sqlite"), nullable=False, default=list)
    save_top_n = db.Column(db.Integer, nullable=False, default=1)
    score_threshold_enabled = db.Column(db.Boolean, nullable=False, default=False)
    score_threshold = db.Column(db.Numeric(10, 2), nullable=True)
    status = db.Column(db.String(32), nullable=False, default="enabled", index=True)
    failure_count = db.Column(db.Integer, nullable=False, default=0)
    last_run_at = db.Column(db.DateTime(timezone=True), nullable=True)
    next_run_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    last_success_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_error_message = db.Column(db.String(512), nullable=True)
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

    user = db.relationship("User", back_populates="scheduled_plans")
    agent_task = db.relationship("AgentTask", back_populates="scheduled_plans")
    runs = db.relationship(
        "ScheduledPlanRun",
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="desc(ScheduledPlanRun.created_at)",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "agentTaskId": self.agent_task_id,
            "agentTaskName": self.agent_task.name if self.agent_task else None,
            "frequencyType": self.frequency_type,
            "timezone": self.timezone,
            "timeOfDay": self.time_of_day.isoformat(timespec="minutes") if self.time_of_day else None,
            "minuteOfHour": self.minute_of_hour,
            "monthDays": self.month_days or [],
            "useLastDay": self.use_last_day,
            "weekdays": self.weekdays or [],
            "saveTopN": self.save_top_n,
            "scoreThresholdEnabled": self.score_threshold_enabled,
            "scoreThreshold": _format_metric(self.score_threshold),
            "status": self.status,
            "failureCount": self.failure_count,
            "lastRunAt": self.last_run_at.isoformat() if self.last_run_at else None,
            "nextRunAt": self.next_run_at.isoformat() if self.next_run_at else None,
            "lastSuccessAt": self.last_success_at.isoformat() if self.last_success_at else None,
            "lastErrorMessage": self.last_error_message,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


def _format_metric(value) -> float | None:
    return round(float(value), 2) if value is not None else None
