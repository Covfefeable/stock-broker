from __future__ import annotations

from math import sqrt

from app.services.strategies.dsl import MIN_ANNUALIZATION_PERIODS


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


def _calculate_annual_return(final_equity: float, initial_capital: float, periods: int) -> float:
    if not initial_capital or final_equity <= 0:
        return 0.0
    total_return = (final_equity / initial_capital) - 1
    if periods < MIN_ANNUALIZATION_PERIODS:
        return total_return
    return (final_equity / initial_capital) ** (252 / periods) - 1


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
