import pytest

from app.services.strategies.metrics import (
    _calculate_annual_return,
    _calculate_annualized_volatility,
    _calculate_daily_returns,
    _calculate_max_drawdown,
    _calculate_sharpe_ratio,
)


def test_daily_returns_and_drawdown() -> None:
    curve = [100, 110, 105, 120, 90]
    assert _calculate_daily_returns(curve) == pytest.approx([0.1, -0.0454545455, 0.1428571429, -0.25])
    assert _calculate_max_drawdown(curve) == 0.25


def test_annual_return_uses_total_return_for_short_periods() -> None:
    assert _calculate_annual_return(120, 100, 10) == pytest.approx(0.2)


def test_annual_return_annualizes_for_long_periods() -> None:
    assert _calculate_annual_return(121, 100, 252) == pytest.approx(0.21)


def test_volatility_and_sharpe_are_zero_for_insufficient_data() -> None:
    assert _calculate_annualized_volatility([0.01]) == 0.0
    assert _calculate_sharpe_ratio([0.01]) == 0.0


def test_sharpe_positive_for_positive_mean_returns() -> None:
    returns = [0.01, 0.02, -0.005, 0.015]
    assert _calculate_annualized_volatility(returns) > 0
    assert _calculate_sharpe_ratio(returns) > 0
