import pytest

from app.services.strategies.dsl import _validate_strategy_config
from app.services.strategies.errors import StrategyError
from app.services.strategies.expression import _evaluate_condition, _evaluate_expression


def variable(name: str, offset: int = 0) -> dict:
    token = {"type": "variable", "name": name}
    if offset:
        token["offset"] = offset
    return token


def number(value: float) -> dict:
    return {"type": "number", "value": value}


def operator(value: str) -> dict:
    return {"type": "operator", "value": value}


def function(name: str, *args: list[dict]) -> dict:
    return {"type": "function", "name": name, "args": list(args)}


def contexts() -> list[dict]:
    return [
        {"close": 10, "ma20": 12, "high": 11, "low": 9, "position_ratio": 0.0},
        {"close": 12, "ma20": 12, "high": 13, "low": 10, "position_ratio": 0.3},
        {"close": 15, "ma20": 13, "high": 16, "low": 11, "position_ratio": 0.6},
        {"close": 13, "ma20": 14, "high": 15, "low": 12, "position_ratio": 0.4},
    ]


def test_expression_respects_precedence_and_parentheses() -> None:
    value = _evaluate_expression(
        [
            variable("close"),
            operator("+"),
            number(2),
            operator("*"),
            number(3),
        ],
        contexts(),
        2,
    )
    assert value == 21

    grouped = _evaluate_expression(
        [
            {"type": "groupStart"},
            variable("close"),
            operator("+"),
            number(2),
            {"type": "groupEnd"},
            operator("*"),
            number(3),
        ],
        contexts(),
        2,
    )
    assert grouped == 51


def test_expression_supports_historical_offset_and_rejects_future_offset() -> None:
    assert _evaluate_expression([variable("close", -1)], contexts(), 2) == 12
    assert _evaluate_expression([variable("close", 1)], contexts(), 2) is None


def test_window_and_change_functions() -> None:
    rows = contexts()
    assert _evaluate_expression([function("avg", [variable("close")], [number(3)])], rows, 2) == pytest.approx(12.3333333333)
    assert _evaluate_expression([function("highest", [variable("high")], [number(3)])], rows, 2) == 16
    assert _evaluate_expression([function("lowest", [variable("low")], [number(3)])], rows, 2) == 9
    assert _evaluate_expression([function("change", [variable("close")], [number(2)])], rows, 2) == 5
    assert _evaluate_expression([function("pct_change", [variable("close")], [number(2)])], rows, 2) == 0.5


def test_cross_operators_use_previous_and_current_values() -> None:
    rows = contexts()
    assert _evaluate_condition(
        {
            "leftExpression": [variable("close")],
            "operator": "cross_over",
            "rightExpression": [variable("ma20")],
        },
        rows,
        2,
    )
    assert _evaluate_condition(
        {
            "leftExpression": [variable("close")],
            "operator": "cross_under",
            "rightExpression": [variable("ma20")],
        },
        rows,
        3,
    )


def test_expression_returns_none_for_division_by_zero_and_bad_groups() -> None:
    assert _evaluate_expression([variable("close"), operator("/"), number(0)], contexts(), 2) is None
    assert _evaluate_expression([{"type": "groupStart"}, variable("close")], contexts(), 2) is None


def test_strategy_validation_rejects_future_variable_reference() -> None:
    config = {
        "entryRules": [
            {
                "action": {"type": "buy", "size": 1},
                "conditions": {
                    "type": "group",
                    "logic": "and",
                    "children": [
                        {
                            "type": "condition",
                            "leftExpression": [variable("close", 1)],
                            "operator": ">",
                            "rightExpression": [number(10)],
                        }
                    ],
                },
            }
        ],
        "exitRules": [
            {
                "action": {"type": "sell", "size": 1},
                "conditions": {
                    "type": "group",
                    "logic": "and",
                    "children": [
                        {
                            "type": "condition",
                            "leftExpression": [variable("close")],
                            "operator": "<",
                            "rightExpression": [number(10)],
                        }
                    ],
                },
            }
        ],
        "risk": {},
    }
    with pytest.raises(StrategyError, match="不允许引用未来数据"):
        _validate_strategy_config(config)
