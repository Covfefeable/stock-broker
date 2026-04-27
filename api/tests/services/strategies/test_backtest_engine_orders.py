from datetime import date, timedelta

from app.services.strategies.engine import _run_strategy_backtest


def make_bars(count: int = 8) -> list[dict]:
    start = date(2026, 1, 1)
    closes = [10, 11, 12, 13, 14, 15, 16, 17]
    return [
        {
            "date": start + timedelta(days=index),
            "open": close,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": 1000,
            "isWarmup": False,
        }
        for index, close in enumerate(closes[:count])
    ]


def condition(left: str, operator: str, right: float) -> dict:
    return {
        "type": "condition",
        "leftExpression": [{"type": "variable", "name": left}],
        "operator": operator,
        "rightExpression": [{"type": "number", "value": right}],
    }


def group(*children: dict, logic: str = "and") -> dict:
    return {"type": "group", "logic": logic, "children": list(children)}


def rule(name: str, side: str, size: float, conditions: dict) -> dict:
    return {"name": name, "action": {"type": side, "size": size}, "conditions": conditions}


def config(entry_rules: list[dict], exit_rules: list[dict], force_close: bool = False) -> dict:
    return {
        "entryRules": entry_rules,
        "exitRules": exit_rules,
        "risk": {"initialCapital": 1000, "forceCloseOnEnd": force_close},
    }


def test_buy_signal_executes_on_next_open_and_can_add_position() -> None:
    result = _run_strategy_backtest(
        make_bars(),
        config(
            [rule("buy30", "buy", 0.3, group(condition("close", ">=", 10)))],
            [rule("sellNever", "sell", 1, group(condition("close", "<", 0)))],
        ),
    )

    buys = [trade for trade in result["trades"] if trade["side"] == "buy"]
    assert [trade["date"] for trade in buys[:3]] == ["2026-01-02", "2026-01-03", "2026-01-04"]
    assert [trade["positionRatio"] for trade in buys[:3]] == [30.0, 61.86, 93.73]
    assert buys[3]["positionRatio"] == 100.0


def test_buy_does_not_exceed_full_position() -> None:
    result = _run_strategy_backtest(
        make_bars(),
        config(
            [rule("buy80", "buy", 0.8, group(condition("close", ">=", 10)))],
            [rule("sellNever", "sell", 1, group(condition("close", "<", 0)))],
        ),
    )
    buys = [trade for trade in result["trades"] if trade["side"] == "buy"]
    assert buys[0]["positionRatio"] == 80.0
    assert buys[1]["positionRatio"] == 100.0
    assert len(buys) == 2


def test_sell_size_larger_than_current_position_only_sells_current_position() -> None:
    result = _run_strategy_backtest(
        make_bars(),
        config(
            [rule("buy30", "buy", 0.3, group(condition("close", "==", 10)))],
            [rule("sell50", "sell", 0.5, group(condition("close", ">=", 11)))],
        ),
    )
    sells = [trade for trade in result["trades"] if trade["side"] == "sell"]
    assert sells[0]["date"] == "2026-01-03"
    assert sells[0]["positionRatio"] == 0.0


def test_rule_order_uses_first_matching_rule() -> None:
    result = _run_strategy_backtest(
        make_bars(),
        config(
            [
                rule("first", "buy", 0.25, group(condition("close", ">=", 10))),
                rule("second", "buy", 0.75, group(condition("close", ">=", 10))),
            ],
            [rule("sellNever", "sell", 1, group(condition("close", "<", 0)))],
        ),
    )
    first_buy = next(trade for trade in result["trades"] if trade["side"] == "buy")
    assert first_buy["positionRatio"] == 25.0
    assert first_buy["reason"] == "first触发"


def test_force_close_uses_last_close_and_marks_trade() -> None:
    result = _run_strategy_backtest(
        make_bars(4),
        config(
            [rule("buyAll", "buy", 1, group(condition("close", "==", 10)))],
            [rule("sellNever", "sell", 1, group(condition("close", "<", 0)))],
            force_close=True,
        ),
    )
    forced = result["trades"][-1]
    assert forced["side"] == "sell"
    assert forced["date"] == "2026-01-04"
    assert forced["price"] == 13
    assert forced["isForcedExit"] is True
