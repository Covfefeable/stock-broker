from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import JSONB

from app.extensions import db


def _metric(value) -> float | None:
    return round(float(value), 2) if value is not None else None


class StrategyEvaluation(db.Model):
    __tablename__ = "strategy_evaluations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    strategy_id = db.Column(db.Integer, db.ForeignKey("strategies.id"), nullable=False, index=True)
    status = db.Column(db.String(32), nullable=False, default="queued", index=True)
    score = db.Column(db.Numeric(10, 2), nullable=True)
    conclusion = db.Column(db.String(32), nullable=True)
    generality_conclusion = db.Column(db.String(64), nullable=True)
    stability_conclusion = db.Column(db.String(64), nullable=True)
    risk_conclusion = db.Column(db.String(64), nullable=True)
    summary = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    celery_task_id = db.Column(db.String(128), nullable=True, index=True)
    strategy_snapshot = db.Column(JSONB().with_variant(db.JSON(), "sqlite"), nullable=False, default=dict)
    report = db.Column(JSONB().with_variant(db.JSON(), "sqlite"), nullable=False, default=dict)
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

    strategy = db.relationship("Strategy")
    user = db.relationship("User")

    __table_args__ = (
        db.UniqueConstraint("user_id", "strategy_id", name="uq_strategy_evaluations_user_strategy"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "strategyId": self.strategy_id,
            "status": self.status,
            "score": _metric(self.score),
            "conclusion": self.conclusion,
            "generalityConclusion": self.generality_conclusion,
            "stabilityConclusion": self.stability_conclusion,
            "riskConclusion": self.risk_conclusion,
            "summary": self.summary,
            "errorMessage": self.error_message,
            "celeryTaskId": self.celery_task_id,
            "report": self.report or {},
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "finishedAt": self.finished_at.isoformat() if self.finished_at else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
