from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from math import sqrt
from typing import Any

from sqlalchemy import asc, desc, func, or_

from app.extensions import db
from app.models.exchange import Exchange
from app.models.index_asset import IndexAsset
from app.models.index_daily_bar import IndexDailyBar
from app.models.stock import Stock
from app.models.stock_daily_bar import StockDailyBar
from app.models.strategy import Strategy
from app.models.user import User
from app.services.stock_adjustment import apply_stock_split_adjustments


class StrategyError(Exception):
    pass


RULE_FIELD_VALUES = {
    "open",
    "high",
    "low",
    "close",
    "volume",
    "ma5",
    "ma10",
    "ma20",
    "ma60",
    "ma120",
    "kdj_k",
    "kdj_d",
    "macd_dif",
    "macd_dea",
    "rsi14",
    "bias_ma20",
    "return_5d",
    "return_20d",
    "return_60d",
    "volume_ratio_5",
    "volume_ratio_20",
    "atr14",
    "volatility_20d",
    "close_pct_of_20d_range",
    "close_pct_of_60d_range",
    "distance_to_20d_high",
    "distance_to_20d_low",
    "body_pct",
    "upper_shadow_pct",
    "lower_shadow_pct",
    "gap_up",
    "gap_down",
    "position_return",
    "holding_days",
    "position_ratio",
}
RULE_OPERATOR_VALUES = {">", ">=", "<", "<=", "==", "!=", "cross_over", "cross_under"}
EXPRESSION_OPERATOR_VALUES = {"+", "-", "*", "/"}
EXPRESSION_FUNCTION_ARITY = {
    "abs": 1,
    "min": 2,
    "max": 2,
    "sum": 2,
    "avg": 2,
    "std": 2,
    "highest": 2,
    "lowest": 2,
    "change": 2,
    "pct_change": 2,
}
WINDOW_FUNCTIONS = {"sum", "avg", "std", "highest", "lowest"}
CHANGE_FUNCTIONS = {"change", "pct_change"}


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

        latest_date_subquery = (
            db.session.query(
                StockDailyBar.exchange_code.label("exchange_code"),
                StockDailyBar.ticker.label("ticker"),
                func.max(StockDailyBar.trade_date).label("latest_date"),
            )
            .group_by(StockDailyBar.exchange_code, StockDailyBar.ticker)
            .subquery()
        )

        rows = (
            db.session.query(Stock, latest_date_subquery.c.latest_date)
            .outerjoin(
                latest_date_subquery,
                (Stock.exchange_code == latest_date_subquery.c.exchange_code)
                & (Stock.ticker == latest_date_subquery.c.ticker),
            )
            .filter(Stock.country_code == normalized_country_code)
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
            "items": [strategy_stock_option(row, latest_date) for row, latest_date in rows],
            "syncHint": None,
            "message": None,
        }

    latest_date_subquery = (
        db.session.query(
            IndexDailyBar.country_code.label("country_code"),
            IndexDailyBar.ticker.label("ticker"),
            func.max(IndexDailyBar.trade_date).label("latest_date"),
        )
        .group_by(IndexDailyBar.country_code, IndexDailyBar.ticker)
        .subquery()
    )

    rows = (
        db.session.query(IndexAsset, latest_date_subquery.c.latest_date)
        .outerjoin(
            latest_date_subquery,
            (IndexAsset.country_code == latest_date_subquery.c.country_code)
            & (IndexAsset.ticker == latest_date_subquery.c.ticker),
        )
        .filter(IndexAsset.country_code == normalized_country_code)
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
        "items": [strategy_index_option(row, latest_date) for row, latest_date in rows],
        "syncHint": None,
        "message": None,
    }


def strategy_stock_option(stock: Stock, latest_date: date | None) -> dict:
    latest_date_text = latest_date.isoformat() if latest_date else None
    label = f"{stock.ticker} - {stock.name}"
    if latest_date_text:
        label = f"{label}（同步至 {latest_date_text}）"
    return {
        "label": label,
        "value": f"{stock.exchange_code}:{stock.ticker}",
        "ticker": stock.ticker,
        "exchangeCode": stock.exchange_code,
        "name": stock.name,
        "latestDate": latest_date_text,
    }


def strategy_index_option(index_asset: IndexAsset, latest_date: date | None) -> dict:
    latest_date_text = latest_date.isoformat() if latest_date else None
    label = f"{index_asset.ticker} - {index_asset.name}"
    if latest_date_text:
        label = f"{label}（同步至 {latest_date_text}）"
    return {
        "label": label,
        "value": index_asset.ticker,
        "ticker": index_asset.ticker,
        "name": index_asset.name,
        "latestDate": latest_date_text,
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
    if not isinstance(strategy_config, dict):
        raise StrategyError("规则配置格式无效。")
    _validate_strategy_config(strategy_config)

    strategy.strategy_config = strategy_config
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
    _validate_strategy_config(strategy_config)

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
        return apply_stock_split_adjustments(bars, exchange_code, ticker)
    return bars


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


def _validate_strategy_config(strategy_config: dict) -> None:
    entry_group = strategy_config.get("entry")
    exit_group = strategy_config.get("exit")
    risk = strategy_config.get("risk")
    if not isinstance(entry_group, dict) or not isinstance(exit_group, dict) or not isinstance(risk, dict):
        raise StrategyError("规则配置缺少买入规则、卖出规则或风控参数。")
    _validate_rule_group(entry_group, "买入规则")
    _validate_rule_group(exit_group, "卖出规则")


def _validate_rule_group(group: dict, label: str) -> None:
    if group.get("type") != "group":
        raise StrategyError(f"{label}条件组格式无效。")
    if group.get("logic") not in {"and", "or"}:
        raise StrategyError(f"{label}条件组逻辑无效。")
    children = group.get("children")
    if not isinstance(children, list) or not children:
        raise StrategyError(f"{label}不能为空。")
    for index, child in enumerate(children, start=1):
        if not isinstance(child, dict):
            raise StrategyError(f"{label}第 {index} 个条件格式无效。")
        if child.get("type") == "group":
            _validate_rule_group(child, f"{label}第 {index} 个子组")
            continue
        if child.get("type") != "condition":
            raise StrategyError(f"{label}第 {index} 个条件类型无效。")
        if child.get("operator") not in RULE_OPERATOR_VALUES:
            raise StrategyError(f"{label}第 {index} 个条件运算符无效。")
        _validate_expression_tokens(child.get("leftExpression"), f"{label}第 {index} 个条件左表达式")
        _validate_expression_tokens(child.get("rightExpression"), f"{label}第 {index} 个条件右表达式")


def _validate_expression_tokens(tokens: Any, label: str) -> None:
    if not isinstance(tokens, list) or not tokens:
        raise StrategyError(f"{label}不能为空。")
    balance = 0
    previous_kind: str | None = None
    for index, token in enumerate(tokens, start=1):
        if not isinstance(token, dict):
            raise StrategyError(f"{label}第 {index} 个片段格式无效。")
        token_type = token.get("type")
        if token_type == "variable":
            _validate_variable_token(token, f"{label}第 {index} 个变量")
            current_kind = "value"
        elif token_type == "number":
            _parse_number_token(token.get("value"), f"{label}第 {index} 个数字")
            current_kind = "value"
        elif token_type == "function":
            _validate_function_token(token, f"{label}第 {index} 个函数")
            current_kind = "value"
        elif token_type == "operator":
            if token.get("value") not in EXPRESSION_OPERATOR_VALUES:
                raise StrategyError(f"{label}第 {index} 个运算符无效。")
            if previous_kind not in {"value", "groupEnd"}:
                raise StrategyError(f"{label}第 {index} 个运算符前缺少值。")
            current_kind = "operator"
        elif token_type == "groupStart":
            balance += 1
            current_kind = "groupStart"
        elif token_type == "groupEnd":
            balance -= 1
            if balance < 0:
                raise StrategyError(f"{label}括号不匹配。")
            if previous_kind not in {"value", "groupEnd"}:
                raise StrategyError(f"{label}第 {index} 个右括号前缺少值。")
            current_kind = "groupEnd"
        else:
            raise StrategyError(f"{label}第 {index} 个片段类型无效。")

        if current_kind in {"value", "groupStart"} and previous_kind in {"value", "groupEnd"}:
            raise StrategyError(f"{label}第 {index} 个片段前缺少运算符。")
        previous_kind = current_kind

    if balance != 0:
        raise StrategyError(f"{label}括号不匹配。")
    if previous_kind in {"operator", "groupStart"}:
        raise StrategyError(f"{label}结尾缺少值。")


def _validate_variable_token(token: dict, label: str) -> None:
    name = token.get("name")
    if name not in RULE_FIELD_VALUES:
        raise StrategyError(f"{label}不支持：{name}。")
    offset = int(token.get("offset") or 0)
    if offset > 0:
        raise StrategyError(f"{label}不允许引用未来数据。")


def _validate_function_token(token: dict, label: str) -> None:
    name = token.get("name")
    expected_arity = EXPRESSION_FUNCTION_ARITY.get(name)
    if expected_arity is None:
        raise StrategyError(f"{label}不支持：{name}。")
    args = token.get("args")
    if not isinstance(args, list) or len(args) != expected_arity:
        raise StrategyError(f"{label}参数数量无效。")
    for index, arg in enumerate(args, start=1):
        _validate_expression_tokens(arg, f"{label}第 {index} 个参数")
    if name in WINDOW_FUNCTIONS | CHANGE_FUNCTIONS:
        window = _literal_number_arg(args[1])
        if window is None or window <= 0 or int(window) != window:
            raise StrategyError(f"{label}窗口周期必须是正整数。")


def _literal_number_arg(tokens: Any) -> float | None:
    if isinstance(tokens, list) and len(tokens) == 1 and isinstance(tokens[0], dict) and tokens[0].get("type") == "number":
        return _parse_number_token(tokens[0].get("value"), "窗口周期")
    return None


def _parse_number_token(value: Any, label: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise StrategyError(f"{label}格式无效。") from exc


def _run_strategy_backtest(bars: list[dict], strategy_config: dict) -> dict:
    indicators = _calculate_indicators(bars)
    risk = strategy_config.get("risk") or {}
    initial_capital = float(risk.get("initialCapital") or 100000)
    position_size = float(risk.get("positionSize") or 1.0)
    stop_loss = float(risk.get("stopLoss") or 0)
    take_profit = float(risk.get("takeProfit") or 0)
    max_holding_days = int(risk.get("maxHoldingDays") or 0)
    force_close_on_end = bool(risk.get("forceCloseOnEnd", True))

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
    context_history: list[dict[str, Any]] = []
    benchmark_entry_price = bars[0]["open"] if bars and bars[0]["open"] is not None else (bars[0]["close"] if bars else None)
    benchmark_shares = (initial_capital / benchmark_entry_price) if benchmark_entry_price and benchmark_entry_price > 0 else 0.0

    for index, bar in enumerate(bars):
        close_price = bar["close"]
        open_price = bar["open"] if bar["open"] is not None else close_price
        if close_price is None:
            equity_curve.append(cash)
            benchmark_curve.append(benchmark_curve[-1] if benchmark_curve else initial_capital)
            continue

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

        context = {
            **bar,
            **{name: series[index] for name, series in indicators.items()},
            "position_return": ((close_price - entry_price) / entry_price) if shares > 0 and entry_price else None,
            "holding_days": (index - entry_index) if shares > 0 and entry_index is not None else None,
            "position_ratio": ((shares * close_price) / (cash + shares * close_price)) if shares > 0 and (cash + shares * close_price) > 0 else 0.0,
        }
        evaluation_contexts = [*context_history, context]
        current_context_index = len(evaluation_contexts) - 1

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

            if risk_reason or _evaluate_group(exit_group, evaluation_contexts, current_context_index):
                pending_sell_signal = True
                pending_exit_reason = risk_reason or "卖出规则触发"

        if not pending_sell_signal and shares <= 0 and _evaluate_group(entry_group, evaluation_contexts, current_context_index):
            pending_buy_signal = True
            pending_entry_reason = "买入规则触发"

        total_equity = cash + shares * close_price
        equity_curve.append(total_equity)
        benchmark_curve.append(benchmark_shares * close_price if benchmark_shares > 0 else initial_capital)
        context_history.append(context.copy())

    live_close_price = bars[-1]["close"] if bars else None
    current_position = {
        "status": "持仓中" if shares > 0 else "空仓",
        "shares": round(shares, 6),
        "entryPrice": round(entry_price, 4) if entry_price is not None else None,
        "positionRatio": round(((shares * live_close_price) / (cash + shares * live_close_price)) * 100, 2)
        if shares > 0 and live_close_price is not None and (cash + shares * live_close_price) > 0
        else 0.0,
        "holdingDays": (len(bars) - 1 - entry_index) if shares > 0 and entry_index is not None else None,
        "unrealizedReturn": round(((live_close_price - entry_price) / entry_price) * 100, 2)
        if shares > 0 and live_close_price is not None and entry_price
        else None,
    }

    if shares > 0 and pending_sell_signal:
        next_action = {
            "action": "下一个交易日开盘卖出",
            "reason": pending_exit_reason or "卖出规则触发",
        }
    elif shares > 0:
        next_action = {
            "action": "继续持有",
            "reason": "当前未触发卖出条件或风控条件。",
        }
    elif pending_buy_signal:
        next_action = {
            "action": "下一个交易日开盘买入",
            "reason": pending_entry_reason or "买入规则触发",
        }
    else:
        next_action = {
            "action": "继续观望",
            "reason": "当前未触发买入条件。",
        }

    if force_close_on_end and shares > 0 and bars[-1]["close"] is not None:
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
        "currentPosition": current_position,
        "nextAction": next_action,
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

    opens = [bar["open"] for bar in bars]
    volumes = [bar["volume"] for bar in bars]

    ma5 = _simple_moving_average(closes, 5)
    ma10 = _simple_moving_average(closes, 10)
    ma20 = _simple_moving_average(closes, 20)
    ma60 = _simple_moving_average(closes, 60)
    ma120 = _simple_moving_average(closes, 120)
    rsi14 = _rsi_wilder(closes, 14)
    macd_dif, macd_dea = _macd(closes)
    kdj_k, kdj_d = _kdj(highs, lows, closes)
    bias_ma20 = _ratio_to_series(closes, ma20)
    return_5d = _rate_of_change(closes, 5)
    return_20d = _rate_of_change(closes, 20)
    return_60d = _rate_of_change(closes, 60)
    volume_ma5 = _simple_moving_average(volumes, 5)
    volume_ma20 = _simple_moving_average(volumes, 20)
    volume_ratio_5 = _series_ratio(volumes, volume_ma5)
    volume_ratio_20 = _series_ratio(volumes, volume_ma20)
    atr14 = _atr(highs, lows, closes, 14)
    volatility_20d = _rolling_volatility(closes, 20)
    high20 = _rolling_max(highs, 20)
    low20 = _rolling_min(lows, 20)
    high60 = _rolling_max(highs, 60)
    low60 = _rolling_min(lows, 60)
    close_pct_of_20d_range = _range_position(closes, low20, high20)
    close_pct_of_60d_range = _range_position(closes, low60, high60)
    distance_to_20d_high = _distance_to_series(closes, high20)
    distance_to_20d_low = _distance_to_series(closes, low20)
    body_pct = _body_pct(opens, closes)
    upper_shadow_pct = _upper_shadow_pct(opens, highs, closes)
    lower_shadow_pct = _lower_shadow_pct(opens, lows, closes)
    gap_up, gap_down = _gap_flags(opens, highs, lows)

    return {
        "ma5": ma5,
        "ma10": ma10,
        "ma20": ma20,
        "ma60": ma60,
        "ma120": ma120,
        "rsi14": rsi14,
        "macd_dif": macd_dif,
        "macd_dea": macd_dea,
        "kdj_k": kdj_k,
        "kdj_d": kdj_d,
        "bias_ma20": bias_ma20,
        "return_5d": return_5d,
        "return_20d": return_20d,
        "return_60d": return_60d,
        "volume_ratio_5": volume_ratio_5,
        "volume_ratio_20": volume_ratio_20,
        "atr14": atr14,
        "volatility_20d": volatility_20d,
        "close_pct_of_20d_range": close_pct_of_20d_range,
        "close_pct_of_60d_range": close_pct_of_60d_range,
        "distance_to_20d_high": distance_to_20d_high,
        "distance_to_20d_low": distance_to_20d_low,
        "body_pct": body_pct,
        "upper_shadow_pct": upper_shadow_pct,
        "lower_shadow_pct": lower_shadow_pct,
        "gap_up": gap_up,
        "gap_down": gap_down,
    }


def _rolling_max(values: list[float | None], window: int) -> list[float | None]:
    result: list[float | None] = []
    for index in range(len(values)):
        window_values = [value for value in values[max(0, index - window + 1) : index + 1] if value is not None]
        result.append(round(max(window_values), 6) if len(window_values) == window else None)
    return result


def _rolling_min(values: list[float | None], window: int) -> list[float | None]:
    result: list[float | None] = []
    for index in range(len(values)):
        window_values = [value for value in values[max(0, index - window + 1) : index + 1] if value is not None]
        result.append(round(min(window_values), 6) if len(window_values) == window else None)
    return result


def _rate_of_change(values: list[float | None], periods: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    for index in range(periods, len(values)):
        current = values[index]
        previous = values[index - periods]
        if current is None or previous in (None, 0):
            continue
        result[index] = round((current / previous) - 1, 6)
    return result


def _ratio_to_series(values: list[float | None], denominator_series: list[float | None]) -> list[float | None]:
    result: list[float | None] = []
    for value, denominator in zip(values, denominator_series, strict=False):
        if value is None or denominator in (None, 0):
            result.append(None)
        else:
            result.append(round((value / denominator) - 1, 6))
    return result


def _series_ratio(values: list[float | None], denominator_series: list[float | None]) -> list[float | None]:
    result: list[float | None] = []
    for value, denominator in zip(values, denominator_series, strict=False):
        if value is None or denominator in (None, 0):
            result.append(None)
        else:
            result.append(round(value / denominator, 6))
    return result


def _distance_to_series(values: list[float | None], base_series: list[float | None]) -> list[float | None]:
    result: list[float | None] = []
    for value, base in zip(values, base_series, strict=False):
        if value is None or base in (None, 0):
            result.append(None)
        else:
            result.append(round((value / base) - 1, 6))
    return result


def _range_position(
    values: list[float | None],
    lows: list[float | None],
    highs: list[float | None],
) -> list[float | None]:
    result: list[float | None] = []
    for value, low, high in zip(values, lows, highs, strict=False):
        if value is None or low is None or high is None:
            result.append(None)
        elif high == low:
            result.append(0.5)
        else:
            result.append(round((value - low) / (high - low), 6))
    return result


def _true_range(high: float, low: float, previous_close: float | None) -> float:
    if previous_close is None:
        return high - low
    return max(high - low, abs(high - previous_close), abs(low - previous_close))


def _atr(highs: list[float | None], lows: list[float | None], closes: list[float | None], period: int) -> list[float | None]:
    true_ranges: list[float | None] = []
    previous_close: float | None = None
    for high, low, close in zip(highs, lows, closes, strict=False):
        if high is None or low is None:
            true_ranges.append(None)
        else:
            true_ranges.append(_true_range(high, low, previous_close))
        if close is not None:
            previous_close = close
    return _simple_moving_average(true_ranges, period)


def _rolling_volatility(closes: list[float | None], window: int) -> list[float | None]:
    daily_returns = _rate_of_change(closes, 1)
    result: list[float | None] = [None] * len(closes)
    for index in range(window, len(closes)):
        window_returns = [value for value in daily_returns[index - window + 1 : index + 1] if value is not None]
        if len(window_returns) != window:
            continue
        mean = sum(window_returns) / window
        variance = sum((item - mean) ** 2 for item in window_returns) / max(window - 1, 1)
        result[index] = round(sqrt(variance), 6)
    return result


def _body_pct(opens: list[float | None], closes: list[float | None]) -> list[float | None]:
    result: list[float | None] = []
    for open_price, close_price in zip(opens, closes, strict=False):
        if open_price in (None, 0) or close_price is None:
            result.append(None)
        else:
            result.append(round(abs(close_price - open_price) / open_price, 6))
    return result


def _upper_shadow_pct(opens: list[float | None], highs: list[float | None], closes: list[float | None]) -> list[float | None]:
    result: list[float | None] = []
    for open_price, high_price, close_price in zip(opens, highs, closes, strict=False):
        if open_price in (None, 0) or high_price is None or close_price is None:
            result.append(None)
        else:
            result.append(round(max(high_price - max(open_price, close_price), 0.0) / open_price, 6))
    return result


def _lower_shadow_pct(opens: list[float | None], lows: list[float | None], closes: list[float | None]) -> list[float | None]:
    result: list[float | None] = []
    for open_price, low_price, close_price in zip(opens, lows, closes, strict=False):
        if open_price in (None, 0) or low_price is None or close_price is None:
            result.append(None)
        else:
            result.append(round(max(min(open_price, close_price) - low_price, 0.0) / open_price, 6))
    return result


def _gap_flags(
    opens: list[float | None],
    highs: list[float | None],
    lows: list[float | None],
) -> tuple[list[float | None], list[float | None]]:
    gap_up: list[float | None] = [None]
    gap_down: list[float | None] = [None]
    for index in range(1, len(opens)):
        open_price = opens[index]
        previous_high = highs[index - 1]
        previous_low = lows[index - 1]
        if open_price is None or previous_high is None or previous_low is None:
            gap_up.append(None)
            gap_down.append(None)
            continue
        gap_up.append(1.0 if open_price > previous_high else 0.0)
        gap_down.append(1.0 if open_price < previous_low else 0.0)
    return gap_up, gap_down


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


def _evaluate_group(group: dict, contexts: list[dict[str, Any]], context_index: int) -> bool:
    children = group.get("children") or []
    logic = group.get("logic", "and")
    if not children:
        return False

    results: list[bool] = []
    for child in children:
        if child.get("type") == "group":
            results.append(_evaluate_group(child, contexts, context_index))
        else:
            results.append(_evaluate_condition(child, contexts, context_index))
    return all(results) if logic == "and" else any(results)


def _evaluate_condition(condition: dict, contexts: list[dict[str, Any]], context_index: int) -> bool:
    left_tokens = condition.get("leftExpression") or []
    right_tokens = condition.get("rightExpression") or []
    left_value = _evaluate_expression(left_tokens, contexts, context_index)
    operator = condition.get("operator")
    right_value = _evaluate_expression(right_tokens, contexts, context_index)

    if operator in {"cross_over", "cross_under"}:
        if context_index <= 0:
            return False
        previous_left = _evaluate_expression(left_tokens, contexts, context_index - 1)
        previous_right = _evaluate_expression(right_tokens, contexts, context_index - 1)
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


def _evaluate_expression(tokens: list[dict], contexts: list[dict[str, Any]], context_index: int) -> float | None:
    output: list[float] = []
    operators: list[str] = []
    precedence = {"+": 1, "-": 1, "*": 2, "/": 2}

    def apply_operator() -> bool:
        if len(output) < 2 or not operators:
            return False
        operator = operators.pop()
        right = output.pop()
        left = output.pop()
        if operator == "+":
            output.append(left + right)
        elif operator == "-":
            output.append(left - right)
        elif operator == "*":
            output.append(left * right)
        elif operator == "/":
            if right == 0:
                return False
            output.append(left / right)
        else:
            return False
        return True

    for token in tokens:
        token_type = token.get("type")
        if token_type in {"variable", "number", "function"}:
            value = _evaluate_value_token(token, contexts, context_index)
            if value is None:
                return None
            output.append(value)
        elif token_type == "operator":
            operator = token.get("value")
            while operators and operators[-1] != "(" and precedence[operators[-1]] >= precedence.get(operator, 0):
                if not apply_operator():
                    return None
            operators.append(operator)
        elif token_type == "groupStart":
            operators.append("(")
        elif token_type == "groupEnd":
            while operators and operators[-1] != "(":
                if not apply_operator():
                    return None
            if not operators or operators[-1] != "(":
                return None
            operators.pop()
        else:
            return None

    while operators:
        if operators[-1] == "(":
            return None
        if not apply_operator():
            return None
    return output[0] if len(output) == 1 else None


def _evaluate_value_token(token: dict, contexts: list[dict[str, Any]], context_index: int) -> float | None:
    token_type = token.get("type")
    if token_type == "number":
        try:
            return float(token.get("value"))
        except (TypeError, ValueError):
            return None
    if token_type == "variable":
        return _resolve_variable_value(token, contexts, context_index)
    if token_type == "function":
        return _evaluate_function_token(token, contexts, context_index)
    return None


def _resolve_variable_value(token: dict, contexts: list[dict[str, Any]], context_index: int) -> float | None:
    name = token.get("name")
    offset = int(token.get("offset") or 0)
    if name not in RULE_FIELD_VALUES or offset > 0:
        return None
    target_index = context_index + offset
    if target_index < 0 or target_index >= len(contexts):
        return None
    value = contexts[target_index].get(name)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _evaluate_function_token(token: dict, contexts: list[dict[str, Any]], context_index: int) -> float | None:
    name = token.get("name")
    args = token.get("args") or []
    if name == "abs":
        value = _evaluate_expression(args[0], contexts, context_index)
        return abs(value) if value is not None else None
    if name in {"min", "max"}:
        left = _evaluate_expression(args[0], contexts, context_index)
        right = _evaluate_expression(args[1], contexts, context_index)
        if left is None or right is None:
            return None
        return min(left, right) if name == "min" else max(left, right)
    if name in WINDOW_FUNCTIONS:
        window = _evaluate_window_arg(args[1], contexts, context_index)
        if window is None or context_index - window + 1 < 0:
            return None
        values = [_evaluate_expression(args[0], contexts, index) for index in range(context_index - window + 1, context_index + 1)]
        if any(value is None for value in values):
            return None
        numeric_values = [float(value) for value in values if value is not None]
        if name == "sum":
            return sum(numeric_values)
        if name == "avg":
            return sum(numeric_values) / len(numeric_values)
        if name == "highest":
            return max(numeric_values)
        if name == "lowest":
            return min(numeric_values)
        average = sum(numeric_values) / len(numeric_values)
        return sqrt(sum((value - average) ** 2 for value in numeric_values) / len(numeric_values))
    if name in CHANGE_FUNCTIONS:
        window = _evaluate_window_arg(args[1], contexts, context_index)
        if window is None or context_index - window < 0:
            return None
        current = _evaluate_expression(args[0], contexts, context_index)
        previous = _evaluate_expression(args[0], contexts, context_index - window)
        if current is None or previous is None:
            return None
        if name == "change":
            return current - previous
        return (current - previous) / previous if previous != 0 else None
    return None


def _evaluate_window_arg(tokens: list[dict], contexts: list[dict[str, Any]], context_index: int) -> int | None:
    value = _evaluate_expression(tokens, contexts, context_index)
    if value is None or value <= 0 or int(value) != value:
        return None
    return int(value)
