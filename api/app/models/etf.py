from datetime import datetime, timezone

from app.extensions import db


class Etf(db.Model):
    __tablename__ = "etfs"

    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(32), nullable=False)
    name = db.Column(db.String(512), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    exchange_id = db.Column(db.Integer, db.ForeignKey("exchanges.id"), nullable=True, index=True)
    exchange_code = db.Column(db.String(16), nullable=False, index=True)
    country_id = db.Column(db.Integer, db.ForeignKey("countries.id"), nullable=True, index=True)
    country_code = db.Column(db.String(8), nullable=True, index=True)
    currency_code = db.Column(db.String(8), nullable=True)
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

    __table_args__ = (
        db.UniqueConstraint("exchange_code", "ticker", name="uq_etfs_exchange_ticker"),
    )

    exchange = db.relationship("Exchange")
    country = db.relationship("Country")

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "name": self.name,
            "isActive": self.is_active,
            "exchangeCode": self.exchange_code,
            "countryCode": self.country_code,
            "currencyCode": self.currency_code,
        }
