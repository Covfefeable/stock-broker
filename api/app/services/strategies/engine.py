from __future__ import annotations

from typing import Any

from app.services.strategies.dsl import _normalize_conflict_policy, _normalize_strategy_rules
from app.services.strategies.errors import StrategyError
from app.services.strategies.expression import _evaluate_group
from app.services.strategies.indicators import _calculate_indicators
from app.services.strategies.metrics import (
    _calculate_annual_return,
    _calculate_annualized_volatility,
    _calculate_daily_returns,
    _calculate_max_drawdown,
    _calculate_sharpe_ratio,
)


def _find_triggered_strategy_rule(rules: list[dict], contexts: list[dict], current_index: int) -> dict | None:
    for rule in rules:
        conditions = rule.get("conditions") or {}
        if _evaluate_group(conditions, contexts, current_index):
            return rule
    return None


def _rule_action_size(rule: dict | None, default: float) -> float:
    if not rule:
        return default
    action = rule.get("action") or {}
    try:
        return max(min(float(action.get("size", default)), 1.0), 0.0)
    except (TypeError, ValueError):
        return default


def _format_rule_reason(rule: dict | None, fallback: str) -> str:
    if not rule:
        return fallback
    name = str(rule.get("name") or "").strip()
    if not name:
        return fallback
    return f"{name}触发"


def _run_strategy_backtest(bars: list[dict], strategy_config: dict) -> dict:
    first_backtest_index = next(
        (index for index, bar in enumerate(bars) if not bar.get("isWarmup")),
        None,
    )
    if first_backtest_index is None:
        raise StrategyError("当前标的没有可用于回测区间的历史日线数据。")
    backtest_bars = bars[first_backtest_index:]
    indicators = _calculate_indicators(bars)
    risk = strategy_config.get("risk") or {}
    initial_capital = float(risk.get("initialCapital") or 100000)
    force_close_on_end = bool(risk.get("forceCloseOnEnd", True))

    entry_rules = _normalize_strategy_rules(strategy_config, "entry")
    exit_rules = _normalize_strategy_rules(strategy_config, "exit")
    conflict_policy = _normalize_conflict_policy(strategy_config)

    cash = initial_capital
    shares = 0.0
    entry_price: float | None = None
    entry_index: int | None = None
    trades: list[dict[str, Any]] = []
    wins = 0
    pending_buy_signal = False
    pending_sell_signal = False
    pending_buy_size = 0.0
    pending_sell_size = 0.0
    pending_entry_reason: str | None = None
    pending_exit_reason: str | None = None
    last_trade_index: int | None = None

    equity_curve: list[float] = []
    benchmark_curve: list[float] = []
    context_history: list[dict[str, Any]] = []
    benchmark_start_bar = bars[first_backtest_index]
    benchmark_entry_price = (
        benchmark_start_bar["open"]
        if benchmark_start_bar["open"] is not None
        else benchmark_start_bar["close"]
    )
    benchmark_shares = (initial_capital / benchmark_entry_price) if benchmark_entry_price and benchmark_entry_price > 0 else 0.0

    for index, bar in enumerate(bars):
        close_price = bar["close"]
        open_price = bar["open"] if bar["open"] is not None else close_price
        if bar.get("isWarmup"):
            context_history.append(
                {
                    **bar,
                    **{name: series[index] for name, series in indicators.items()},
                    "position_return": None,
                    "holding_days": None,
                    "position_ratio": 0.0,
                    "days_since_last_trade": None,
                }
            )
            continue
        if close_price is None or close_price <= 0:
            equity_curve.append(equity_curve[-1] if equity_curve else cash)
            benchmark_curve.append(benchmark_curve[-1] if benchmark_curve else initial_capital)
            continue

        if shares > 0 and pending_sell_signal and open_price is not None and open_price > 0:
            total_equity_at_open = cash + shares * open_price
            current_position_value = shares * open_price
            normalized_sell_size = max(min(pending_sell_size or 1.0, 1.0), 0.0)
            target_sell_value = current_position_value if normalized_sell_size >= 1.0 else total_equity_at_open * normalized_sell_size
            sell_value = min(current_position_value, target_sell_value)
            sell_shares = sell_value / open_price if open_price > 0 else 0.0
            proceeds = sell_shares * open_price
            cash += proceeds
            pnl_ratio = ((open_price - entry_price) / entry_price) if entry_price else 0.0
            if pnl_ratio > 0:
                wins += 1
            remaining_shares = max(0.0, shares - sell_shares)
            next_position_ratio = (
                (remaining_shares * open_price) / (cash + remaining_shares * open_price) * 100
                if remaining_shares > 0 and cash + remaining_shares * open_price > 0
                else 0.0
            )
            trades.append(
                {
                    "date": bar["date"].isoformat(),
                    "side": "sell",
                    "price": round(open_price, 4),
                    "shares": round(sell_shares, 6),
                    "positionRatio": round(next_position_ratio, 2),
                    "return": round(pnl_ratio * 100, 2),
                    "reason": pending_exit_reason or "卖出规则触发",
                }
            )
            shares = remaining_shares
            last_trade_index = index
            if shares <= 1e-8:
                shares = 0.0
                entry_price = None
                entry_index = None
            pending_sell_signal = False
            pending_sell_size = 0.0
            pending_exit_reason = None
        elif pending_sell_signal and (open_price is None or open_price <= 0):
            pending_sell_signal = False
            pending_sell_size = 0.0
            pending_exit_reason = None

        if pending_buy_signal and open_price is not None and open_price > 0:
            normalized_position_size = max(min(pending_buy_size, 1.0), 0.0)
            total_equity_at_open = cash + shares * open_price
            current_position_ratio = (
                (shares * open_price) / total_equity_at_open
                if shares > 0 and total_equity_at_open > 0
                else 0.0
            )
            available_position_ratio = max(0.0, 1.0 - current_position_ratio)
            order_position_ratio = min(normalized_position_size, available_position_ratio)
            investable_cash = total_equity_at_open * order_position_ratio

            if (
                order_position_ratio > 0
                and cash + 1e-6 >= investable_cash
                and investable_cash > 0
            ):
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
                last_trade_index = index
            pending_buy_signal = False
            pending_buy_size = 0.0
            pending_entry_reason = None
        elif pending_buy_signal and (open_price is None or open_price <= 0):
            pending_buy_signal = False
            pending_buy_size = 0.0
            pending_entry_reason = None

        context = {
            **bar,
            **{name: series[index] for name, series in indicators.items()},
            "position_return": ((close_price - entry_price) / entry_price) if shares > 0 and entry_price else None,
            "holding_days": (index - entry_index) if shares > 0 and entry_index is not None else None,
            "position_ratio": ((shares * close_price) / (cash + shares * close_price)) if shares > 0 and (cash + shares * close_price) > 0 else 0.0,
            "days_since_last_trade": (index - last_trade_index) if last_trade_index is not None else None,
        }
        evaluation_contexts = [*context_history, context]
        current_context_index = len(evaluation_contexts) - 1

        total_equity_for_signal = cash + shares * close_price
        current_position_ratio_for_signal = (
            (shares * close_price) / total_equity_for_signal
            if shares > 0 and total_equity_for_signal > 0
            else 0.0
        )
        triggered_exit_rule = (
            _find_triggered_strategy_rule(exit_rules, evaluation_contexts, current_context_index)
            if shares > 0
            else None
        )
        triggered_entry_rule = _find_triggered_strategy_rule(entry_rules, evaluation_contexts, current_context_index)
        has_signal_conflict = triggered_exit_rule is not None and triggered_entry_rule is not None
        normalized_position_size_for_signal = _rule_action_size(triggered_entry_rule, 0.0)
        available_position_ratio_for_signal = max(0.0, 1.0 - current_position_ratio_for_signal)
        can_add_position = normalized_position_size_for_signal > 0 and available_position_ratio_for_signal > 1e-6

        should_queue_sell = triggered_exit_rule is not None
        should_queue_buy = triggered_entry_rule is not None and can_add_position
        if has_signal_conflict:
            if conflict_policy == "entry_first":
                should_queue_sell = False
            elif conflict_policy == "allow_reentry":
                should_queue_buy = normalized_position_size_for_signal > 0
            elif conflict_policy == "skip":
                should_queue_sell = False
                should_queue_buy = False
            else:
                should_queue_buy = False

        if should_queue_sell and triggered_exit_rule:
            pending_sell_signal = True
            pending_sell_size = _rule_action_size(triggered_exit_rule, 1.0)
            pending_exit_reason = _format_rule_reason(triggered_exit_rule, "卖出规则触发")
        if should_queue_buy and triggered_entry_rule:
            pending_buy_signal = True
            pending_buy_size = normalized_position_size_for_signal
            pending_entry_reason = _format_rule_reason(triggered_entry_rule, "买入规则触发")

        total_equity = cash + shares * close_price
        equity_curve.append(total_equity)
        benchmark_curve.append(benchmark_shares * close_price if benchmark_shares > 0 else initial_capital)
        context_history.append(context.copy())

    if force_close_on_end and shares > 0 and backtest_bars[-1]["close"] is not None and backtest_bars[-1]["close"] > 0:
        close_price = backtest_bars[-1]["close"]
        proceeds = shares * close_price
        cash += proceeds
        pnl_ratio = ((close_price - entry_price) / entry_price) if entry_price else 0.0
        trades.append(
                {
                    "date": backtest_bars[-1]["date"].isoformat(),
                    "side": "sell",
                    "price": round(close_price, 4),
                    "shares": round(shares, 6),
                    "positionRatio": 0.0,
                    "return": round(pnl_ratio * 100, 2),
                    "reason": "回测结束强制平仓",
                    "isForcedExit": True,
                }
            )
        shares = 0.0
        equity_curve[-1] = cash

    final_equity = equity_curve[-1] if equity_curve else initial_capital
    total_return_ratio = (final_equity / initial_capital) - 1 if initial_capital else 0.0
    periods = max(len(equity_curve) - 1, 1)
    annual_return_ratio = _calculate_annual_return(final_equity, initial_capital, periods)
    max_drawdown_ratio = _calculate_max_drawdown(equity_curve)
    benchmark_final = benchmark_curve[-1] if benchmark_curve else initial_capital
    benchmark_return_ratio = (benchmark_final / initial_capital) - 1 if initial_capital else 0.0
    benchmark_annual_return_ratio = _calculate_annual_return(benchmark_final, initial_capital, periods)
    daily_returns = _calculate_daily_returns(equity_curve)
    benchmark_daily_returns = _calculate_daily_returns(benchmark_curve)
    volatility_ratio = _calculate_annualized_volatility(daily_returns)
    benchmark_volatility_ratio = _calculate_annualized_volatility(benchmark_daily_returns)
    sharpe_ratio = _calculate_sharpe_ratio(daily_returns)
    benchmark_sharpe_ratio = _calculate_sharpe_ratio(benchmark_daily_returns)
    benchmark_max_drawdown_ratio = _calculate_max_drawdown(benchmark_curve)
    sell_trades = [trade for trade in trades if trade["side"] == "sell" and not trade.get("isForcedExit")]
    benchmark_up_days = sum(1 for item in benchmark_daily_returns if item > 0)
    benchmark_win_rate = (benchmark_up_days / len(benchmark_daily_returns) * 100) if benchmark_daily_returns else 0.0

    return {
        "annualReturn": round(annual_return_ratio * 100, 2),
        "benchmarkAnnualReturn": round(benchmark_annual_return_ratio * 100, 2),
        "totalReturn": round(total_return_ratio * 100, 2),
        "maxDrawdown": round(max_drawdown_ratio * 100, 2),
        "benchmarkMaxDrawdown": round(benchmark_max_drawdown_ratio * 100, 2),
        "tradeCount": len(sell_trades),
        "benchmarkTradeCount": 1 if benchmark_curve else 0,
        "winRate": round((wins / len(sell_trades) * 100), 2) if sell_trades else 0.0,
        "benchmarkWinRate": round(benchmark_win_rate, 2),
        "initialCapital": round(initial_capital, 2),
        "finalEquity": round(final_equity, 2),
        "benchmarkReturn": round(benchmark_return_ratio * 100, 2),
        "volatility": round(volatility_ratio * 100, 2),
        "benchmarkVolatility": round(benchmark_volatility_ratio * 100, 2),
        "sharpe": round(sharpe_ratio, 2),
        "benchmarkSharpe": round(benchmark_sharpe_ratio, 2),
        "equityCurve": [
            {"date": bar["date"].isoformat(), "value": round(value, 2)}
            for bar, value in zip(backtest_bars, equity_curve, strict=False)
        ],
        "benchmarkCurve": [
            {"date": bar["date"].isoformat(), "value": round(value, 2)}
            for bar, value in zip(backtest_bars, benchmark_curve, strict=False)
        ],
        "trades": trades,
        "dateRange": {
            "start": backtest_bars[0]["date"].isoformat() if backtest_bars else None,
            "end": backtest_bars[-1]["date"].isoformat() if backtest_bars else None,
        },
    }
