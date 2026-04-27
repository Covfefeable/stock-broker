from __future__ import annotations

from datetime import date
from typing import Any

from app.models.index_daily_bar import IndexDailyBar
from app.models.stock_daily_bar import StockDailyBar
from app.services.stock_adjustment import apply_stock_split_adjustments
from app.services.strategies.dsl import INDICATOR_WARMUP_BARS
from app.services.strategies.errors import StrategyError


def _load_asset_bars(asset_type: str, asset_identifier: str, country_code: str, strategy_config: dict) -> list[dict]:
    risk = strategy_config.get("risk") or {}
    start_date = _parse_date(risk.get("backtestStartDate"))
    end_date = _parse_date(risk.get("backtestEndDate"))

    if asset_type == "stock":
        if ":" not in asset_identifier:
            raise StrategyError("股票标的格式无效。")
        exchange_code, ticker = asset_identifier.split(":", 1)
        model = StockDailyBar
        query = model.query.filter(model.exchange_code == exchange_code, model.ticker == ticker)
    else:
        model = IndexDailyBar
        query = model.query.filter(model.country_code == country_code, model.ticker == asset_identifier)

    if end_date:
        query = query.filter(model.trade_date <= end_date)

    rows = query.order_by(model.trade_date.asc()).all()
    bars = [
        {
            "date": row.trade_date,
            "open": _to_float(row.open),
            "high": _to_float(row.high),
            "low": _to_float(row.low),
            "close": _to_float(row.close),
            "volume": float(row.volume) if row.volume is not None else None,
        }
        for row in rows
        if row.trade_date and row.close is not None
    ]
    if asset_type == "stock":
        bars = apply_stock_split_adjustments(bars, exchange_code, ticker)
    return _attach_warmup_flags(bars, start_date)


def _attach_warmup_flags(bars: list[dict], start_date: date | None) -> list[dict]:
    if not start_date:
        return [dict(bar, isWarmup=False) for bar in bars]

    first_backtest_index: int | None = None
    for index, bar in enumerate(bars):
        if bar["date"] >= start_date:
            first_backtest_index = index
            break
    if first_backtest_index is None:
        return []

    warmup_start_index = max(0, first_backtest_index - INDICATOR_WARMUP_BARS)
    selected = bars[warmup_start_index:]
    return [
        dict(bar, isWarmup=bar["date"] < start_date)
        for bar in selected
    ]


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise StrategyError("回测日期格式无效。") from exc


def _to_float(value: Any) -> float | None:
    return float(value) if value is not None else None
