from datetime import datetime, timezone

from app.extensions import db


class Exchange(db.Model):
    __tablename__ = "exchanges"

    id = db.Column(db.Integer, primary_key=True)
    exchange_code = db.Column(db.String(16), nullable=False, unique=True, index=True)
    exchange_name = db.Column(db.String(160), nullable=False)
    exchange_name_short = db.Column(db.String(80), nullable=True)
    country_id = db.Column(db.Integer, db.ForeignKey("countries.id"), nullable=True, index=True)
    country_code = db.Column(db.String(8), nullable=True, index=True)
    currency_code = db.Column(db.String(8), nullable=True)
    local_open = db.Column(db.String(16), nullable=True)
    local_close = db.Column(db.String(16), nullable=True)
    beijing_open = db.Column(db.String(16), nullable=True)
    beijing_close = db.Column(db.String(16), nullable=True)
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

    country = db.relationship("Country")

    def to_dict(self) -> dict:
        return {
            "exchangeCode": self.exchange_code,
            "exchangeName": self.exchange_name,
            "exchangeNameShort": self.exchange_name_short,
            "countryCode": self.country_code,
            "currencyCode": self.currency_code,
            "localOpen": self.local_open,
            "localClose": self.local_close,
            "beijingOpen": self.beijing_open,
            "beijingClose": self.beijing_close,
            "timezone": self.timezone,
            "delay": self.delay,
            "notes": self.notes,
        }
