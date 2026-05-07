from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import JSONB

from app.extensions import db


class AgentIteration(db.Model):
    __tablename__ = "agent_iterations"

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("agent_tasks.id"), nullable=False, index=True)
    iteration_number = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(32), nullable=False, default="success")
    annual_return = db.Column(db.Numeric(10, 2), nullable=True)
    max_drawdown = db.Column(db.Numeric(10, 2), nullable=True)
    sharpe = db.Column(db.Numeric(10, 2), nullable=True)
    strategy_config = db.Column(
        JSONB().with_variant(db.JSON(), "sqlite"),
        nullable=False,
        default=dict,
    )
    intent = db.Column(db.String(64), nullable=True)
    memory = db.Column(db.Text, nullable=True)
    time_robustness = db.Column(
        JSONB().with_variant(db.JSON(), "sqlite"),
        nullable=True,
        default=dict,
    )
    equity_preview = db.Column(
        JSONB().with_variant(db.JSON(), "sqlite"),
        nullable=True,
        default=dict,
    )
    analysis = db.Column(db.Text, nullable=True)
    action_plan = db.Column(db.Text, nullable=True)
    summary = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    task = db.relationship("AgentTask", back_populates="iterations")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "iterationNumber": self.iteration_number,
            "status": self.status,
            "annualReturn": _format_metric(self.annual_return),
            "maxDrawdown": _format_metric(self.max_drawdown),
            "sharpe": _format_metric(self.sharpe),
            "strategyConfig": self.strategy_config or {},
            "intent": self.intent,
            "memory": self.memory,
            "timeRobustness": self.time_robustness or {},
            "equityPreview": self.equity_preview or {},
            "analysis": self.analysis,
            "actionPlan": self.action_plan,
            "summary": self.summary,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


def _format_metric(value) -> float | None:
    return round(float(value), 2) if value is not None else None
