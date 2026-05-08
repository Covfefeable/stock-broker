from __future__ import annotations

from math import sqrt
from typing import Any

from app.services.strategies.dsl import CHANGE_FUNCTIONS, RULE_FIELD_VALUES, WINDOW_FUNCTIONS


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
    precedence = {"+": 1, "-": 1, "*": 2, "/": 2, "u+": 3, "u-": 3}
    previous_kind: str | None = None

    def apply_operator() -> bool:
        if not operators:
            return False
        operator = operators.pop()
        if operator in {"u+", "u-"}:
            if not output:
                return False
            value = output.pop()
            output.append(value if operator == "u+" else -value)
            return True
        if len(output) < 2:
            return False
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
            previous_kind = "value"
        elif token_type == "operator":
            operator = token.get("value")
            if operator in {"+", "-"} and previous_kind in {None, "operator", "groupStart"}:
                operator = f"u{operator}"
            while operators and operators[-1] != "(" and precedence[operators[-1]] >= precedence.get(operator, 0):
                if not apply_operator():
                    return None
            operators.append(operator)
            previous_kind = "operator"
        elif token_type == "groupStart":
            operators.append("(")
            previous_kind = "groupStart"
        elif token_type == "groupEnd":
            while operators and operators[-1] != "(":
                if not apply_operator():
                    return None
            if not operators or operators[-1] != "(":
                return None
            operators.pop()
            previous_kind = "value"
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
    try:
        offset = int(token.get("offset") or 0)
    except (TypeError, ValueError):
        return None
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
        variance = sum((value - average) ** 2 for value in numeric_values) / len(numeric_values)
        standard_deviation = sqrt(variance)
        if name == "std":
            return standard_deviation
        if name == "ema":
            return _ema_window_value(numeric_values)
        if name == "pct_slope":
            return _linear_pct_slope(numeric_values)
        if name == "zscore":
            return 0.0 if standard_deviation == 0 else (numeric_values[-1] - average) / standard_deviation
        if name == "percentile_rank":
            current = numeric_values[-1]
            lower_count = sum(1 for value in numeric_values if value < current)
            equal_count = sum(1 for value in numeric_values if value == current)
            return (lower_count + 0.5 * equal_count) / len(numeric_values)
        if name == "drawdown_from_high":
            highest_value = max(numeric_values)
            return (numeric_values[-1] / highest_value) - 1 if highest_value != 0 else None
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


def _ema_window_value(values: list[float]) -> float | None:
    if not values:
        return None
    multiplier = 2 / (len(values) + 1)
    ema_value = values[0]
    for value in values[1:]:
        ema_value = (value - ema_value) * multiplier + ema_value
    return ema_value


def _linear_pct_slope(values: list[float]) -> float | None:
    count = len(values)
    if count < 2:
        return None
    current_value = values[-1]
    if current_value == 0:
        return None
    x_mean = (count - 1) / 2
    y_mean = sum(values) / count
    denominator = sum((index - x_mean) ** 2 for index in range(count))
    if denominator == 0:
        return 0.0
    numerator = sum((index - x_mean) * (value - y_mean) for index, value in enumerate(values))
    return (numerator / denominator) / current_value
