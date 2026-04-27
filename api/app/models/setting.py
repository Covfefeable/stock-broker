from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import JSONB

from app.extensions import db
from app.services.scoring import default_performance_score_weights


def default_ai_models() -> list[dict[str, str]]:
    return [
        {
            "name": "OpenAI",
            "model": "gpt-4.1",
            "baseUrl": "https://api.openai.com/v1",
            "apiKey": "",
        }
    ]


class Setting(db.Model):
    __tablename__ = "settings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True, index=True)
    canghai_api_key = db.Column(db.Text, nullable=True)
    canghai_token_check_enabled = db.Column(db.Boolean, nullable=False, default=True)
    ai_models = db.Column(
        JSONB().with_variant(db.JSON(), "sqlite"),
        nullable=False,
        default=default_ai_models,
    )
    performance_score_weights = db.Column(
        JSONB().with_variant(db.JSON(), "sqlite"),
        nullable=False,
        default=default_performance_score_weights,
    )
    notification_data_sync = db.Column(db.Boolean, nullable=False, default=False)
    notification_agent_goal = db.Column(db.Boolean, nullable=False, default=False)
    notification_backtest = db.Column(db.Boolean, nullable=False, default=False)
    keep_signed_in = db.Column(db.Boolean, nullable=False, default=True)
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

    user = db.relationship("User", back_populates="settings")

    def to_dict(self) -> dict:
        return {
            "dataSource": {
                "canghaiApiKey": self.canghai_api_key or "",
                "canghaiTokenCheckEnabled": self.canghai_token_check_enabled,
            },
            "ai": {
                "models": self.ai_models or default_ai_models(),
            },
            "notifications": {
                "dataSync": self.notification_data_sync,
                "agentGoal": self.notification_agent_goal,
                "backtest": self.notification_backtest,
            },
            "scoring": {
                "performanceScoreWeights": self.performance_score_weights or default_performance_score_weights(),
            },
            "account": {
                "keepSignedIn": self.keep_signed_in,
            },
        }
