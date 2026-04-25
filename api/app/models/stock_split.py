from datetime import date, datetime, timezone
from decimal import Decimal

from app.extensions import db


class StockSplit(db.Model):
    __tablename__ = "stock_splits"

    id = db.Column(db.Integer, primary_key=True)
    stock_id = db.Column(db.Integer, db.ForeignKey("stocks.id"), nullable=True, index=True)
    exchange_code = db.Column(db.String(16), nullable=False, index=True)
    ticker = db.Column(db.String(32), nullable=False, index=True)
    event_date = db.Column(db.Date, nullable=False, index=True)
    split_factor = db.Column(db.Numeric(20, 6), nullable=False)
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
            "ticker",
            "event_date",
            name="uq_stock_splits_exchange_ticker_date",
        ),
    )

    stock = db.relationship("Stock")

    def to_dict(self) -> dict:
        return {
            "exchangeCode": self.exchange_code,
            "ticker": self.ticker,
            "date": self.event_date.isoformat() if isinstance(self.event_date, date) else None,
            "splitFactor": decimal_to_float(self.split_factor),
        }


def decimal_to_float(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None
