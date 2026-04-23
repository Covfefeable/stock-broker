from datetime import datetime, timezone

from app.extensions import db


class Country(db.Model):
    __tablename__ = "countries"

    id = db.Column(db.Integer, primary_key=True)
    country_code = db.Column(db.String(8), nullable=False, unique=True, index=True)
    country_name = db.Column(db.String(120), nullable=False)
    timezone = db.Column(db.String(120), nullable=True)
    delay = db.Column(db.String(64), nullable=True)
    notes = db.Column(db.String(255), nullable=True)
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

    def to_dict(self) -> dict:
        return {
            "countryCode": self.country_code,
            "countryName": self.country_name,
            "timezone": self.timezone,
            "delay": self.delay,
            "notes": self.notes,
        }
