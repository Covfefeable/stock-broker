from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from app.models.stock_dividend import StockDividend
from app.models.stock_split import StockSplit


PRICE_FIELDS = ("open", "high", "low", "close")


def apply_stock_split_adjustments(
    bars: list[dict[str, Any]], exchange_code: str, ticker: str
) -> list[dict[str, Any]]:
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
    dividend_events = _load_dividend_events(exchange_code, ticker)
    close_by_date = {
        trade_date: float(bar["close"])
        for bar in bars
        if (trade_date := _parse_date(bar.get("date"))) and bar.get("close") is not None
    }
    dividend_price_factors = _calculate_dividend_price_factors(dividend_events, close_by_date)
    if not events and not dividend_price_factors:
        return [
            dict(bar, adjustmentFactor=1.0, priceAdjustmentFactor=1.0, volumeAdjustmentFactor=1.0)
            for bar in bars
        ]

    adjusted: list[dict[str, Any]] = []
    for bar in bars:
        trade_date = _parse_date(bar.get("date"))
        cumulative_split_factor = 1.0
        dividend_factor = 1.0
        if trade_date:
            for event_date, event_split_factor in events:
                if trade_date < event_date:
                    cumulative_split_factor *= event_split_factor
            for event_date, price_factor in dividend_price_factors:
                if trade_date < event_date:
                    dividend_factor *= price_factor

        next_bar = dict(bar)
        price_factor = cumulative_split_factor * dividend_factor
        next_bar["adjustmentFactor"] = price_factor
        next_bar["priceAdjustmentFactor"] = price_factor
        next_bar["volumeAdjustmentFactor"] = cumulative_split_factor
        if price_factor != 1.0:
            for field in PRICE_FIELDS:
                next_bar[field] = _divide(next_bar.get(field), price_factor)
        if cumulative_split_factor != 1.0:
            next_bar["volume"] = _multiply(next_bar.get("volume"), cumulative_split_factor)
        adjusted.append(next_bar)

    return adjusted


def _load_dividend_events(exchange_code: str, ticker: str) -> list[tuple[date, float]]:
    dividends = (
        StockDividend.query.filter(
            StockDividend.exchange_code == exchange_code,
            StockDividend.ticker == ticker,
            StockDividend.dividend.isnot(None),
        )
        .order_by(StockDividend.event_date.asc(), StockDividend.id.asc())
        .all()
    )
    return [
        (row.event_date, float(row.dividend))
        for row in dividends
        if row.event_date and row.dividend and float(row.dividend) > 0
    ]


def _calculate_dividend_price_factors(
    dividend_events: list[tuple[date, float]],
    close_by_date: dict[date, float],
) -> list[tuple[date, float]]:
    factors: list[tuple[date, float]] = []
    sorted_dates = sorted(close_by_date)
    for event_date, dividend in dividend_events:
        previous_dates = [trade_date for trade_date in sorted_dates if trade_date < event_date]
        if not previous_dates:
            continue
        previous_close = close_by_date.get(previous_dates[-1])
        if not previous_close or previous_close <= dividend:
            continue
        factors.append((event_date, previous_close / (previous_close - dividend)))
    return factors


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
