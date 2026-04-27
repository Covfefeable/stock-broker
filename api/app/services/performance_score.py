from __future__ import annotations

from typing import Any

ANNUAL_RETURN_WEIGHT = 0.7
SHARPE_WEIGHT = 5
MAX_DRAWDOWN_WEIGHT = 0.3


def default_performance_score_weights() -> dict[str, float]:
    return {
        "annualReturn": ANNUAL_RETURN_WEIGHT,
        "sharpe": SHARPE_WEIGHT,
        "maxDrawdown": MAX_DRAWDOWN_WEIGHT,
    }


def normalize_performance_score_weights(value: Any) -> dict[str, float]:
    defaults = default_performance_score_weights()
    if not isinstance(value, dict):
        return defaults
    return {
        "annualReturn": _to_weight(value.get("annualReturn"), defaults["annualReturn"]),
        "sharpe": _to_weight(value.get("sharpe"), defaults["sharpe"], minimum=1, maximum=10),
        "maxDrawdown": _to_weight(value.get("maxDrawdown"), defaults["maxDrawdown"]),
    }


def calculate_performance_score(
    annual_return: Any,
    sharpe: Any,
    max_drawdown: Any,
    *,
    weights: dict[str, float] | None = None,
) -> float:
    """Shared strategy quality score used by Agent and backtest evaluation."""
    normalized_weights = normalize_performance_score_weights(weights)
    return (
        _to_float(annual_return) * normalized_weights["annualReturn"]
        + _to_float(sharpe) * normalized_weights["sharpe"]
        - _to_float(max_drawdown) * normalized_weights["maxDrawdown"]
    )


def _to_weight(value: Any, fallback: float, *, minimum: float = 0, maximum: float | None = None) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    if number < minimum:
        return minimum
    if maximum is not None and number > maximum:
        return maximum
    return number


def _to_float(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
