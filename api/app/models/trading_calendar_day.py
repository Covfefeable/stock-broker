from datetime import date, datetime, timezone

from app.extensions import db


class TradingCalendarDay(db.Model):
    __tablename__ = "trading_calendar_days"

    id = db.Column(db.Integer, primary_key=True)
    exchange_id = db.Column(db.Integer, db.ForeignKey("exchanges.id"), nullable=True, index=True)
    exchange_code = db.Column(db.String(16), nullable=False, index=True)
    trade_date = db.Column(db.Date, nullable=False, index=True)
    status = db.Column(db.Integer, nullable=False, default=1)
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
        db.UniqueConstraint(
            "exchange_code",
            "trade_date",
            name="uq_trading_calendar_days_exchange_date",
        ),
    )

    exchange = db.relationship("Exchange")

    def to_dict(self) -> dict:
        return {
            "exchangeCode": self.exchange_code,
            "date": self.trade_date.isoformat() if isinstance(self.trade_date, date) else None,
            "status": self.status,
        }
