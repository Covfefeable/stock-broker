from datetime import date, datetime, timezone
from decimal import Decimal

from app.extensions import db


class StockDailyBar(db.Model):
    __tablename__ = "stock_daily_bars"

    id = db.Column(db.Integer, primary_key=True)
    stock_id = db.Column(db.Integer, db.ForeignKey("stocks.id"), nullable=True, index=True)
    exchange_code = db.Column(db.String(16), nullable=False, index=True)
    ticker = db.Column(db.String(32), nullable=False, index=True)
    trade_date = db.Column(db.Date, nullable=False, index=True)
    open = db.Column(db.Numeric(20, 6), nullable=True)
    high = db.Column(db.Numeric(20, 6), nullable=True)
    low = db.Column(db.Numeric(20, 6), nullable=True)
    close = db.Column(db.Numeric(20, 6), nullable=True)
    volume = db.Column(db.BigInteger, nullable=True)
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
            "trade_date",
            name="uq_stock_daily_bars_exchange_ticker_date",
        ),
    )

    stock = db.relationship("Stock")

    def to_dict(self) -> dict:
        return {
            "exchangeCode": self.exchange_code,
            "ticker": self.ticker,
            "date": self.trade_date.isoformat() if isinstance(self.trade_date, date) else None,
            "open": decimal_to_float(self.open),
            "high": decimal_to_float(self.high),
            "low": decimal_to_float(self.low),
            "close": decimal_to_float(self.close),
            "volume": self.volume,
        }


def decimal_to_float(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None
