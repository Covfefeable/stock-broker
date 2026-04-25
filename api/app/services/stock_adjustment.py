from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from app.models.stock_split import StockSplit


PRICE_FIELDS = ("open", "high", "low", "close")


def apply_stock_split_adjustments(bars: list[dict[str, Any]], exchange_code: str, ticker: str) -> list[dict[str, Any]]:
    if not bars:
        return []

    splits = (
        StockSplit.query.filter(
            StockSplit.exchange_code == exchange_code,
            StockSplit.ticker == ticker,
            StockSplit.split_factor.isnot(None),
        )
        .order_by(StockSplit.event_date.asc(), StockSplit.id.asc())
        .all()
    )
    events = [
        (row.event_date, float(row.split_factor))
        for row in splits
        if row.event_date and row.split_factor and float(row.split_factor) > 0
    ]
    if not events:
        return [dict(bar, adjustmentFactor=1.0) for bar in bars]

    adjusted: list[dict[str, Any]] = []
    for bar in bars:
        trade_date = _parse_date(bar.get("date"))
        factor = 1.0
        if trade_date:
            for event_date, split_factor in events:
                if trade_date < event_date:
                    factor *= split_factor

        next_bar = dict(bar)
        next_bar["adjustmentFactor"] = factor
        if factor != 1.0:
            for field in PRICE_FIELDS:
                next_bar[field] = _divide(next_bar.get(field), factor)
            next_bar["volume"] = _multiply(next_bar.get("volume"), factor)
        adjusted.append(next_bar)

    return adjusted


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    return date.fromisoformat(str(value))


def _divide(value: Any, factor: float) -> float | None:
    if value is None:
        return None
    return float(Decimal(str(value)) / Decimal(str(factor)))


def _multiply(value: Any, factor: float) -> int | None:
    if value is None:
        return None
    return int(round(float(Decimal(str(value)) * Decimal(str(factor)))))
