from datetime import datetime, timezone

from app.extensions import db


class UserDataSourceStatus(db.Model):
    __tablename__ = "user_data_source_statuses"
    __table_args__ = (
        db.UniqueConstraint("user_id", "source_key", name="uq_user_data_source_status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    source_key = db.Column(db.String(64), nullable=False, index=True)
    source_name = db.Column(db.String(128), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="unknown")
    token_status = db.Column(db.String(32), nullable=False, default="unknown")
    last_checked_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_success_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_failed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    latency_ms = db.Column(db.Integer, nullable=True)
    http_status = db.Column(db.Integer, nullable=True)
    message = db.Column(db.String(255), nullable=True)
    failure_count = db.Column(db.Integer, nullable=False, default=0)
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

    user = db.relationship("User", back_populates="data_source_statuses")

    def to_dict(self) -> dict:
        return {
            "sourceKey": self.source_key,
            "sourceName": self.source_name,
            "status": self.status,
            "tokenStatus": self.token_status,
            "lastCheckedAt": self.last_checked_at.isoformat() if self.last_checked_at else None,
            "lastSuccessAt": self.last_success_at.isoformat() if self.last_success_at else None,
            "lastFailedAt": self.last_failed_at.isoformat() if self.last_failed_at else None,
            "latencyMs": self.latency_ms,
            "httpStatus": self.http_status,
            "message": self.message,
            "failureCount": self.failure_count,
        }
