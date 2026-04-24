from datetime import datetime, timezone

from app.extensions import db


class DataSourceStatus(db.Model):
    __tablename__ = "data_source_statuses"

    id = db.Column(db.Integer, primary_key=True)
    source_key = db.Column(db.String(64), nullable=False, unique=True, index=True)
    source_name = db.Column(db.String(128), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="unknown")
    latency_ms = db.Column(db.Integer, nullable=True)
    checked_at = db.Column(db.DateTime(timezone=True), nullable=True)
    http_status = db.Column(db.Integer, nullable=True)
    message = db.Column(db.String(255), nullable=True)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self) -> dict:
        return {
            "sourceKey": self.source_key,
            "sourceName": self.source_name,
            "status": self.status,
            "latencyMs": self.latency_ms,
            "checkedAt": self.checked_at.isoformat() if self.checked_at else None,
            "httpStatus": self.http_status,
            "message": self.message,
        }
