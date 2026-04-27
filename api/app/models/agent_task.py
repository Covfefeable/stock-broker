from datetime import date, datetime, timezone

from sqlalchemy.dialects.postgresql import JSONB

from app.extensions import db


class AgentTask(db.Model):
    __tablename__ = "agent_tasks"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    country_code = db.Column(db.String(8), nullable=False, index=True)
    asset_type = db.Column(db.String(16), nullable=False, index=True)
    asset_identifier = db.Column(db.String(64), nullable=False)
    asset_name = db.Column(db.String(255), nullable=False)
    ai_model_name = db.Column(db.String(255), nullable=False)
    ai_model_config = db.Column(
        JSONB().with_variant(db.JSON(), "sqlite"),
        nullable=False,
        default=dict,
    )
    note = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(32), nullable=False, default="queued", index=True)
    stop_requested = db.Column(db.Boolean, nullable=False, default=False, index=True)
    stop_requested_at = db.Column(db.DateTime(timezone=True), nullable=True)
    max_iterations = db.Column(db.Integer, nullable=False, default=10)
    current_iteration = db.Column(db.Integer, nullable=False, default=0)
    target_annual_return = db.Column(db.Numeric(10, 2), nullable=False)
    max_drawdown_limit = db.Column(db.Numeric(10, 2), nullable=False)
    min_sharpe = db.Column(db.Numeric(10, 2), nullable=False)
    initial_capital = db.Column(db.Numeric(14, 2), nullable=False)
    position_size = db.Column(db.Numeric(8, 4), nullable=False)
    stop_loss = db.Column(db.Numeric(8, 4), nullable=False)
    take_profit = db.Column(db.Numeric(8, 4), nullable=False)
    min_add_position_interval = db.Column(db.Integer, nullable=False, default=3)
    max_holding_days = db.Column(db.Integer, nullable=False)
    backtest_start_date = db.Column(db.Date, nullable=False)
    backtest_end_date = db.Column(db.Date, nullable=False)
    best_annual_return = db.Column(db.Numeric(10, 2), nullable=True)
    best_sharpe = db.Column(db.Numeric(10, 2), nullable=True)
    best_strategy_config = db.Column(
        JSONB().with_variant(db.JSON(), "sqlite"),
        nullable=True,
    )
    best_summary = db.Column(db.Text, nullable=True)
    celery_task_id = db.Column(db.String(128), nullable=True, index=True)
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

    user = db.relationship("User", back_populates="agent_tasks")
    iterations = db.relationship(
        "AgentIteration",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="desc(AgentIteration.iteration_number)",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "countryCode": self.country_code,
            "assetType": self.asset_type,
            "assetIdentifier": self.asset_identifier,
            "assetName": self.asset_name,
            "aiModelName": self.ai_model_name,
            "aiModelConfig": self.ai_model_config or {},
            "note": self.note,
            "status": self.status,
            "stopRequested": self.stop_requested,
            "stopRequestedAt": self.stop_requested_at.isoformat() if self.stop_requested_at else None,
            "maxIterations": self.max_iterations,
            "currentIteration": self.current_iteration,
            "targetAnnualReturn": _format_metric(self.target_annual_return),
            "maxDrawdownLimit": _format_metric(self.max_drawdown_limit),
            "minSharpe": _format_metric(self.min_sharpe),
            "backtestStartDate": self.backtest_start_date.isoformat() if isinstance(self.backtest_start_date, date) else None,
            "backtestEndDate": self.backtest_end_date.isoformat() if isinstance(self.backtest_end_date, date) else None,
            "bestAnnualReturn": _format_metric(self.best_annual_return),
            "bestSharpe": _format_metric(self.best_sharpe),
            "bestStrategyConfig": self.best_strategy_config or None,
            "bestSummary": self.best_summary,
            "celeryTaskId": self.celery_task_id,
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "finishedAt": self.finished_at.isoformat() if self.finished_at else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


def _format_metric(value) -> float | None:
    return round(float(value), 2) if value is not None else None
