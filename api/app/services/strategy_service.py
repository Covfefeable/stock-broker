from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from math import sqrt
from typing import Any

from sqlalchemy import asc, desc, or_

from app.extensions import db
from app.models.exchange import Exchange
from app.models.index_asset import IndexAsset
from app.models.index_daily_bar import IndexDailyBar
from app.models.stock import Stock
from app.models.stock_daily_bar import StockDailyBar
from app.models.strategy import Strategy
from app.models.user import User


class StrategyError(Exception):
    pass


def _parse_optional_metric(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except Exception as exc:  # noqa: BLE001
        raise StrategyError("收益预览结果格式无效。") from exc


def list_strategy_asset_options(country_code: str, asset_type: str) -> dict:
    normalized_country_code = country_code.strip().upper()
    if not normalized_country_code:
        raise StrategyError("请先选择国家/地区。")
    if asset_type not in {"stock", "index"}:
        raise StrategyError("请选择股票或指数。")

    if asset_type == "stock":
        exchanges = (
            Exchange.query.filter(Exchange.country_code == normalized_country_code)
            .order_by(Exchange.exchange_name.asc())
            .all()
        )
        if not exchanges:
            return {
                "items": [],
                "syncHint": "exchange_list",
                "message": "当前国家/地区还没有交易所清单，请先同步交易所数据。",
            }

        rows = (
            Stock.query.filter(Stock.country_code == normalized_country_code)
            .order_by(Stock.exchange_code.asc(), Stock.ticker.asc())
            .all()
        )
        if not rows:
            return {
                "items": [],
                "syncHint": "stock_list",
                "message": "当前国家/地区还没有股票清单，请先在数据中心同步对应交易所的股票数据。",
            }

        return {
            "items": [
                {
                    "label": f"{row.ticker} - {row.name}",
                    "value": f"{row.exchange_code}:{row.ticker}",
                    "ticker": row.ticker,
                    "exchangeCode": row.exchange_code,
                    "name": row.name,
                }
                for row in rows
            ],
            "syncHint": None,
            "message": None,
        }

    rows = (
        IndexAsset.query.filter(IndexAsset.country_code == normalized_country_code)
        .order_by(IndexAsset.ticker.asc())
        .all()
    )
    if not rows:
        return {
            "items": [],
            "syncHint": "index_list",
            "message": "当前国家/地区还没有指数清单，请先同步指数数据。",
        }

    return {
        "items": [
            {
                "label": f"{row.ticker} - {row.name}",
                "value": row.ticker,
                "ticker": row.ticker,
                "name": row.name,
            }
            for row in rows
        ],
        "syncHint": None,
        "message": None,
    }


def list_strategies(
    user: User,
    *,
    keyword: str = "",
    country_region: str = "",
    source: str = "",
    status: str = "",
    page: int = 1,
    page_size: int = 10,
    sort_field: str = "updatedAt",
    sort_order: str = "descend",
) -> dict:
    query = Strategy.query.filter(Strategy.user_id == user.id)

    normalized_keyword = keyword.strip()
    if normalized_keyword:
        pattern = f"%{normalized_keyword}%"
        query = query.filter(
            or_(
                Strategy.name.ilike(pattern),
                Strategy.type.ilike(pattern),
                Strategy.country_region.ilike(pattern),
            )
        )

    if country_region:
        query = query.filter(Strategy.country_region == country_region)
    if source:
        query = query.filter(Strategy.source == source)
    if status:
        query = query.filter(Strategy.status == status)

    if sort_field == "annualReturn":
        order_column = Strategy.annual_return
        query = query.order_by(
            asc(order_column).nullslast() if sort_order == "ascend" else desc(order_column).nullslast()
        )
    else:
        order_column = Strategy.updated_at
        query = query.order_by(asc(order_column) if sort_order == "ascend" else desc(order_column))

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    country_region_options = [
        value
        for value in db.session.query(Strategy.country_region)
        .filter(Strategy.user_id == user.id)
        .distinct()
        .order_by(Strategy.country_region.asc())
        .all()
    ]
    source_options = [
        value
        for value in db.session.query(Strategy.source)
        .filter(Strategy.user_id == user.id)
        .distinct()
        .order_by(Strategy.source.asc())
        .all()
    ]
    status_options = [
        value
        for value in db.session.query(Strategy.status)
        .filter(Strategy.user_id == user.id)
        .distinct()
        .order_by(Strategy.status.asc())
        .all()
    ]

    return {
        "items": [item.to_dict() for item in items],
        "pagination": {
            "page": page,
            "pageSize": page_size,
            "total": total,
        },
        "filters": {
            "countryRegions": [value for (value,) in country_region_options if value],
            "sources": [value for (value,) in source_options if value],
            "statuses": [value for (value,) in status_options if value],
        },
    }


def get_strategy(user: User, strategy_id: int) -> Strategy:
    strategy = Strategy.query.filter(
        Strategy.id == strategy_id,
        Strategy.user_id == user.id,
    ).first()
    if not strategy:
        raise StrategyError("未找到对应的策略。")
    return strategy


def archive_strategy(user: User, strategy_id: int) -> Strategy:
    strategy = get_strategy(user, strategy_id)
    strategy.status = "已归档"
    strategy.archived_at = datetime.now(timezone.utc)
    strategy.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return strategy


def delete_strategy(user: User, strategy_id: int) -> None:
    strategy = get_strategy(user, strategy_id)
    db.session.delete(strategy)
    db.session.commit()


def update_strategy(user: User, strategy_id: int, payload: dict) -> Strategy:
    strategy = get_strategy(user, strategy_id)
    _apply_strategy_payload(strategy, payload)
    strategy.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return strategy


def create_strategy(user: User, payload: dict) -> Strategy:
    strategy = Strategy(user_id=user.id)
    _apply_strategy_payload(strategy, payload, is_create=True)
    strategy.status = strategy.status or "草稿"
    db.session.add(strategy)
    db.session.commit()
    return strategy


def _apply_strategy_payload(strategy: Strategy, payload: dict, *, is_create: bool = False) -> None:
    name = str(payload.get("name", "")).strip()
    strategy_type = str(payload.get("type", "")).strip()
    source = str(payload.get("source", "")).strip()
    country_region = str(payload.get("countryRegion", "")).strip()
    asset_type = str(payload.get("assetType", "")).strip()
    asset_identifier = str(payload.get("assetIdentifier", "")).strip()
    asset_name = str(payload.get("assetName", "")).strip()
    strategy_config = payload.get("strategyConfig") or {}
    annual_return = _parse_optional_metric(payload.get("annualReturn"))
    max_drawdown = _parse_optional_metric(payload.get("maxDrawdown"))

    if not name:
        raise StrategyError("请输入策略名称。")
    if not strategy_type:
        raise StrategyError("请选择策略类型。")
    if source != "人工创建":
        raise StrategyError("请选择有效的来源。")
    if not country_region:
        raise StrategyError("请选择国家/地区。")
    if asset_type not in {"stock", "index"}:
        raise StrategyError("请选择股票或指数。")
    if not asset_identifier:
        raise StrategyError("请选择具体标的。")

    strategy.name = name
    strategy.type = strategy_type
    strategy.source = source
    strategy.country_region = country_region
    strategy.asset_type = asset_type
    strategy.asset_identifier = asset_identifier
    strategy.asset_name = asset_name or None
    strategy.strategy_config = strategy_config if isinstance(strategy_config, dict) else {}
    strategy.annual_return = annual_return
    strategy.max_drawdown = max_drawdown
    if is_create and not strategy.status:
        strategy.status = "草稿"


def preview_strategy(user: User, payload: dict) -> dict:
    asset_type = str(payload.get("assetType", "")).strip()
    asset_identifier = str(payload.get("assetIdentifier", "")).strip()
    country_code = str(payload.get("countryCode", "")).strip().upper()
    strategy_config = payload.get("strategyConfig") or {}
    strategy_id = payload.get("strategyId")

    if asset_type not in {"stock", "index"}:
        raise StrategyError("请选择股票或指数。")
    if not asset_identifier:
        raise StrategyError("请选择具体标的。")
    if asset_type == "index" and not country_code:
        raise StrategyError("请选择国家/地区。")
    if not isinstance(strategy_config, dict):
        raise StrategyError("规则配置格式无效。")

    bars = _load_asset_bars(asset_type, asset_identifier, country_code, strategy_config)
    if not bars:
        raise StrategyError("当前标的没有可用于预览收益的历史日线数据。")

    preview = _run_strategy_backtest(bars, strategy_config)

    if strategy_id:
        strategy = get_strategy(user, int(strategy_id))
        strategy.annual_return = Decimal(str(preview["annualReturn"]))
        strategy.max_drawdown = Decimal(str(preview["maxDrawdown"]))
        strategy.updated_at = datetime.now(timezone.utc)
        db.session.commit()

    return preview


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

    if start_date:
        query = query.filter(model.trade_date >= start_date)
    if end_date:
        query = query.filter(model.trade_date <= end_date)

    rows = query.order_by(model.trade_date.asc()).all()
    return [
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


def _run_strategy_backtest(bars: list[dict], strategy_config: dict) -> dict:
    indicators = _calculate_indicators(bars)
    risk = strategy_config.get("risk") or {}
    initial_capital = float(risk.get("initialCapital") or 100000)
    position_size = float(risk.get("positionSize") or 1.0)
    stop_loss = float(risk.get("stopLoss") or 0)
    take_profit = float(risk.get("takeProfit") or 0)
    max_holding_days = int(risk.get("maxHoldingDays") or 0)

    entry_group = strategy_config.get("entry") or {}
    exit_group = strategy_config.get("exit") or {}

    cash = initial_capital
    shares = 0.0
    entry_price: float | None = None
    entry_index: int | None = None
    trades: list[dict[str, Any]] = []
    wins = 0
    pending_buy_signal = False
    pending_sell_signal = False
    pending_entry_reason: str | None = None
    pending_exit_reason: str | None = None

    equity_curve: list[float] = []
    benchmark_curve: list[float] = []
    benchmark_entry_price = bars[0]["open"] if bars and bars[0]["open"] is not None else (bars[0]["close"] if bars else None)
    benchmark_shares = (initial_capital / benchmark_entry_price) if benchmark_entry_price and benchmark_entry_price > 0 else 0.0

    for index, bar in enumerate(bars):
        close_price = bar["close"]
        open_price = bar["open"] if bar["open"] is not None else close_price
        if close_price is None:
            equity_curve.append(cash)
            benchmark_curve.append(benchmark_curve[-1] if benchmark_curve else initial_capital)
            continue

        if pending_buy_signal and open_price is not None:
            normalized_position_size = max(min(position_size, 1.0), 0.0)
            total_equity_at_open = cash + shares * open_price
            current_position_ratio = (
                (shares * open_price) / total_equity_at_open
                if shares > 0 and total_equity_at_open > 0
                else 0.0
            )
            available_position_ratio = max(0.0, 1.0 - current_position_ratio)
            order_position_ratio = min(normalized_position_size, available_position_ratio)
            investable_cash = total_equity_at_open * order_position_ratio

            if order_position_ratio > 0 and cash >= investable_cash and investable_cash > 0:
                new_shares = investable_cash / open_price
                existing_cost = (entry_price or 0.0) * shares
                total_shares = shares + new_shares
                total_cost = existing_cost + investable_cash

                cash -= investable_cash
                shares = total_shares
                entry_price = total_cost / total_shares if total_shares > 0 else None
                if entry_index is None:
                    entry_index = index

                trades.append(
                    {
                        "date": bar["date"].isoformat(),
                        "side": "buy",
                        "price": round(open_price, 4),
                        "shares": round(new_shares, 6),
                        "positionRatio": round(((shares * open_price) / total_equity_at_open) * 100, 2)
                        if total_equity_at_open > 0
                        else 0.0,
                        "reason": pending_entry_reason or "买入规则触发",
                    }
                )
            pending_buy_signal = False
            pending_entry_reason = None

        if shares > 0 and pending_sell_signal and open_price is not None:
            proceeds = shares * open_price
            cash += proceeds
            pnl_ratio = ((open_price - entry_price) / entry_price) if entry_price else 0.0
            if pnl_ratio > 0:
                wins += 1
            trades.append(
                {
                    "date": bar["date"].isoformat(),
                    "side": "sell",
                    "price": round(open_price, 4),
                    "shares": round(shares, 6),
                    "positionRatio": 0.0,
                    "return": round(pnl_ratio * 100, 2),
                    "reason": pending_exit_reason or "卖出规则触发",
                }
            )
            shares = 0.0
            entry_price = None
            entry_index = None
            pending_sell_signal = False
            pending_exit_reason = None

        context = {
            **bar,
            **{name: series[index] for name, series in indicators.items()},
            "position_return": ((close_price - entry_price) / entry_price) if shares > 0 and entry_price else None,
            "holding_days": (index - entry_index) if shares > 0 and entry_index is not None else None,
            "position_ratio": ((shares * close_price) / (cash + shares * close_price)) if shares > 0 and (cash + shares * close_price) > 0 else 0.0,
        }
        previous_context = None
        if index > 0:
            previous_bar = bars[index - 1]
            previous_context = {
                **previous_bar,
                **{name: series[index - 1] for name, series in indicators.items()},
                "position_return": None,
                "holding_days": None,
            }

        if shares > 0:
            position_return = context["position_return"]
            holding_days = context["holding_days"]
            risk_reason: str | None = None
            if stop_loss and position_return is not None and position_return <= -abs(stop_loss):
                risk_reason = "止损触发"
            if take_profit and position_return is not None and position_return >= abs(take_profit):
                risk_reason = "止盈触发"
            if max_holding_days and holding_days is not None and holding_days >= max_holding_days:
                risk_reason = "最大持仓天数触发"

            if risk_reason or _evaluate_group(exit_group, context, previous_context):
                pending_sell_signal = True
                pending_exit_reason = risk_reason or "卖出规则触发"

        if _evaluate_group(entry_group, context, previous_context):
            pending_buy_signal = True
            pending_entry_reason = "买入规则触发"

        total_equity = cash + shares * close_price
        equity_curve.append(total_equity)
        benchmark_curve.append(benchmark_shares * close_price if benchmark_shares > 0 else initial_capital)

    if shares > 0 and bars[-1]["close"] is not None:
        close_price = bars[-1]["close"]
        proceeds = shares * close_price
        cash += proceeds
        pnl_ratio = ((close_price - entry_price) / entry_price) if entry_price else 0.0
        if pnl_ratio > 0:
            wins += 1
        trades.append(
                {
                    "date": bars[-1]["date"].isoformat(),
                    "side": "sell",
                    "price": round(close_price, 4),
                    "shares": round(shares, 6),
                    "positionRatio": 0.0,
                    "return": round(pnl_ratio * 100, 2),
                    "reason": "回测结束强制平仓",
                }
            )
        shares = 0.0
        equity_curve[-1] = cash

    final_equity = equity_curve[-1] if equity_curve else initial_capital
    total_return_ratio = (final_equity / initial_capital) - 1 if initial_capital else 0.0
    periods = max(len(equity_curve) - 1, 1)
    annual_return_ratio = (final_equity / initial_capital) ** (252 / periods) - 1 if initial_capital and final_equity > 0 else 0.0
    max_drawdown_ratio = _calculate_max_drawdown(equity_curve)
    benchmark_final = benchmark_curve[-1] if benchmark_curve else initial_capital
    benchmark_return_ratio = (benchmark_final / initial_capital) - 1 if initial_capital else 0.0
    benchmark_annual_return_ratio = (
        (benchmark_final / initial_capital) ** (252 / periods) - 1
        if initial_capital and benchmark_final > 0
        else 0.0
    )
    daily_returns = _calculate_daily_returns(equity_curve)
    benchmark_daily_returns = _calculate_daily_returns(benchmark_curve)
    volatility_ratio = _calculate_annualized_volatility(daily_returns)
    benchmark_volatility_ratio = _calculate_annualized_volatility(benchmark_daily_returns)
    sharpe_ratio = _calculate_sharpe_ratio(daily_returns)
    benchmark_sharpe_ratio = _calculate_sharpe_ratio(benchmark_daily_returns)
    benchmark_max_drawdown_ratio = _calculate_max_drawdown(benchmark_curve)
    sell_trades = [trade for trade in trades if trade["side"] == "sell"]

    return {
        "annualReturn": round(annual_return_ratio * 100, 2),
        "benchmarkAnnualReturn": round(benchmark_annual_return_ratio * 100, 2),
        "totalReturn": round(total_return_ratio * 100, 2),
        "maxDrawdown": round(max_drawdown_ratio * 100, 2),
        "benchmarkMaxDrawdown": round(benchmark_max_drawdown_ratio * 100, 2),
        "tradeCount": len(sell_trades),
        "benchmarkTradeCount": 1 if benchmark_curve else 0,
        "winRate": round((wins / len(sell_trades) * 100), 2) if sell_trades else 0.0,
        "benchmarkWinRate": 100.0 if benchmark_curve and benchmark_return_ratio > 0 else 0.0,
        "initialCapital": round(initial_capital, 2),
        "finalEquity": round(final_equity, 2),
        "benchmarkReturn": round(benchmark_return_ratio * 100, 2),
        "volatility": round(volatility_ratio * 100, 2),
        "benchmarkVolatility": round(benchmark_volatility_ratio * 100, 2),
        "sharpe": round(sharpe_ratio, 2),
        "benchmarkSharpe": round(benchmark_sharpe_ratio, 2),
        "equityCurve": [
            {"date": bar["date"].isoformat(), "value": round(value, 2)}
            for bar, value in zip(bars, equity_curve, strict=False)
        ],
        "benchmarkCurve": [
            {"date": bar["date"].isoformat(), "value": round(value, 2)}
            for bar, value in zip(bars, benchmark_curve, strict=False)
        ],
        "trades": trades,
        "dateRange": {
            "start": bars[0]["date"].isoformat() if bars else None,
            "end": bars[-1]["date"].isoformat() if bars else None,
        },
    }


def _calculate_max_drawdown(equity_curve: list[float]) -> float:
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    max_drawdown = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - value) / peak)
    return max_drawdown


def _calculate_daily_returns(equity_curve: list[float]) -> list[float]:
    returns: list[float] = []
    for previous, current in zip(equity_curve, equity_curve[1:], strict=False):
        if previous <= 0:
            returns.append(0.0)
        else:
            returns.append((current / previous) - 1)
    return returns


def _calculate_annualized_volatility(daily_returns: list[float]) -> float:
    if len(daily_returns) < 2:
        return 0.0
    mean = sum(daily_returns) / len(daily_returns)
    variance = sum((daily_return - mean) ** 2 for daily_return in daily_returns) / (len(daily_returns) - 1)
    return sqrt(variance) * sqrt(252)


def _calculate_sharpe_ratio(daily_returns: list[float]) -> float:
    if len(daily_returns) < 2:
        return 0.0
    mean = sum(daily_returns) / len(daily_returns)
    variance = sum((daily_return - mean) ** 2 for daily_return in daily_returns) / (len(daily_returns) - 1)
    std = sqrt(variance)
    if std == 0:
        return 0.0
    return (mean / std) * sqrt(252)


def _calculate_indicators(bars: list[dict]) -> dict[str, list[float | None]]:
    closes = [bar["close"] for bar in bars]
    highs = [bar["high"] for bar in bars]
    lows = [bar["low"] for bar in bars]

    ma5 = _simple_moving_average(closes, 5)
    ma20 = _simple_moving_average(closes, 20)
    rsi14 = _rsi_wilder(closes, 14)
    macd_dif, macd_dea = _macd(closes)
    kdj_k, kdj_d = _kdj(highs, lows, closes)

    return {
        "ma5": ma5,
        "ma20": ma20,
        "rsi14": rsi14,
        "macd_dif": macd_dif,
        "macd_dea": macd_dea,
        "kdj_k": kdj_k,
        "kdj_d": kdj_d,
    }


def _simple_moving_average(values: list[float | None], window: int) -> list[float | None]:
    result: list[float | None] = []
    for index in range(len(values)):
        window_values = [value for value in values[max(0, index - window + 1) : index + 1] if value is not None]
        result.append(round(sum(window_values) / window, 6) if len(window_values) == window else None)
    return result


def _ema(values: list[float | None], period: int) -> list[float | None]:
    result: list[float | None] = []
    multiplier = 2 / (period + 1)
    ema_value: float | None = None
    for value in values:
        if value is None:
            result.append(ema_value)
            continue
        ema_value = value if ema_value is None else (value - ema_value) * multiplier + ema_value
        result.append(round(ema_value, 6))
    return result


def _macd(values: list[float | None]) -> tuple[list[float | None], list[float | None]]:
    ema12 = _ema(values, 12)
    ema26 = _ema(values, 26)
    dif = [
        round(fast - slow, 6) if fast is not None and slow is not None else None
        for fast, slow in zip(ema12, ema26, strict=False)
    ]
    dea = _ema(dif, 9)
    return dif, dea


def _rsi_wilder(values: list[float | None], period: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return result

    deltas: list[float] = []
    for index in range(1, len(values)):
        current = values[index]
        previous = values[index - 1]
        if current is None or previous is None:
            deltas.append(0.0)
        else:
            deltas.append(current - previous)

    gains = [max(delta, 0.0) for delta in deltas]
    losses = [abs(min(delta, 0.0)) for delta in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    result[period] = 100.0 if avg_loss == 0 else round(100 - (100 / (1 + avg_gain / avg_loss)), 6)

    for index in range(period + 1, len(values)):
        gain = gains[index - 1]
        loss = losses[index - 1]
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period
        result[index] = 100.0 if avg_loss == 0 else round(100 - (100 / (1 + avg_gain / avg_loss)), 6)

    return result


def _kdj(
    highs: list[float | None],
    lows: list[float | None],
    closes: list[float | None],
    period: int = 9,
) -> tuple[list[float | None], list[float | None]]:
    k_values: list[float | None] = []
    d_values: list[float | None] = []
    prev_k = 50.0
    prev_d = 50.0

    for index in range(len(closes)):
        close = closes[index]
        window_highs = [value for value in highs[max(0, index - period + 1) : index + 1] if value is not None]
        window_lows = [value for value in lows[max(0, index - period + 1) : index + 1] if value is not None]
        if close is None or len(window_highs) < period or len(window_lows) < period:
            k_values.append(None)
            d_values.append(None)
            continue

        highest = max(window_highs)
        lowest = min(window_lows)
        rsv = 50.0 if highest == lowest else ((close - lowest) / (highest - lowest)) * 100
        prev_k = (2 / 3) * prev_k + (1 / 3) * rsv
        prev_d = (2 / 3) * prev_d + (1 / 3) * prev_k
        k_values.append(round(prev_k, 6))
        d_values.append(round(prev_d, 6))

    return k_values, d_values


def _evaluate_group(group: dict, context: dict[str, Any], previous_context: dict[str, Any] | None) -> bool:
    children = group.get("children") or []
    logic = group.get("logic", "and")
    if not children:
        return False

    results: list[bool] = []
    for child in children:
        if child.get("type") == "group":
            results.append(_evaluate_group(child, context, previous_context))
        else:
            results.append(_evaluate_condition(child, context, previous_context))
    return all(results) if logic == "and" else any(results)


def _evaluate_condition(condition: dict, context: dict[str, Any], previous_context: dict[str, Any] | None) -> bool:
    left_value = context.get(condition.get("leftField"))
    operator = condition.get("operator")
    right_mode = condition.get("rightMode")
    right_value = context.get(condition.get("rightField")) if right_mode == "field" else condition.get("rightValue")

    if operator in {"cross_over", "cross_under"}:
        if previous_context is None:
            return False
        previous_left = previous_context.get(condition.get("leftField"))
        previous_right = previous_context.get(condition.get("rightField"))
        if None in {left_value, right_value, previous_left, previous_right}:
            return False
        if operator == "cross_over":
            return previous_left <= previous_right and left_value > right_value
        return previous_left >= previous_right and left_value < right_value

    if left_value is None or right_value is None:
        return False
    if operator == ">":
        return left_value > right_value
    if operator == ">=":
        return left_value >= right_value
    if operator == "<":
        return left_value < right_value
    if operator == "<=":
        return left_value <= right_value
    if operator == "==":
        return left_value == right_value
    if operator == "!=":
        return left_value != right_value
    return False
