from datetime import datetime, timezone

from app.extensions import db


class EventLog(db.Model):
    __tablename__ = "event_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    event_type = db.Column(db.String(64), nullable=False, index=True)
    event_name = db.Column(db.String(128), nullable=False)
    task_id = db.Column(db.String(128), nullable=True, index=True)
    show_in_ui = db.Column(db.Boolean, nullable=False, default=True, index=True)
    source = db.Column(db.String(64), nullable=True)
    target = db.Column(db.String(64), nullable=True)
    status = db.Column(db.String(32), nullable=False, index=True)
    level = db.Column(db.String(32), nullable=False, default="info")
    message = db.Column(db.Text, nullable=False)
    http_status = db.Column(db.Integer, nullable=True)
    records_affected = db.Column(db.Integer, nullable=True)
    started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    finished_at = db.Column(db.DateTime(timezone=True), nullable=True)
    duration_ms = db.Column(db.Integer, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship("User")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "time": self.created_at.isoformat() if self.created_at else None,
            "eventType": self.event_type,
            "eventName": self.event_name,
            "taskId": self.task_id,
            "showInUi": self.show_in_ui,
            "source": self.source,
            "target": self.target,
            "status": self.status,
            "level": self.level,
            "message": self.message,
            "httpStatus": self.http_status,
            "recordsAffected": self.records_affected,
            "durationMs": self.duration_ms,
        }
