from app.services.scoring import (
    calculate_performance_score,
    default_performance_score_weights,
    normalize_performance_score_weights,
)


def test_default_performance_score_weights() -> None:
    assert default_performance_score_weights() == {
        "annualReturn": 0.7,
        "sharpe": 5,
        "maxDrawdown": 0.3,
    }


def test_calculate_performance_score_uses_weights() -> None:
    assert calculate_performance_score(10, 1.2, 8) == 10 * 0.7 + 1.2 * 5 - 8 * 0.3
    assert calculate_performance_score(
        10,
        1.2,
        8,
        weights={"annualReturn": 1, "sharpe": 2, "maxDrawdown": 0.5},
    ) == 10 + 2.4 - 4


def test_normalize_performance_score_weights_clamps_sharpe_weight() -> None:
    assert normalize_performance_score_weights({"annualReturn": -1, "sharpe": 99, "maxDrawdown": -2}) == {
        "annualReturn": 0,
        "sharpe": 10,
        "maxDrawdown": 0,
    }
