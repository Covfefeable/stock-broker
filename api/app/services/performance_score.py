from __future__ import annotations

from typing import Any

ANNUAL_RETURN_WEIGHT = 0.7
SHARPE_WEIGHT = 10
MAX_DRAWDOWN_WEIGHT = 0.2


def calculate_performance_score(annual_return: Any, sharpe: Any, max_drawdown: Any) -> float:
    """Shared strategy quality score used by Agent and backtest evaluation."""
    return (
        _to_float(annual_return) * ANNUAL_RETURN_WEIGHT
        + _to_float(sharpe) * SHARPE_WEIGHT
        - _to_float(max_drawdown) * MAX_DRAWDOWN_WEIGHT
    )


def _to_float(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
