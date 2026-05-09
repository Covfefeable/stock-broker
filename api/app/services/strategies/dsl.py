from __future__ import annotations

from typing import Any

from app.services.strategies.errors import StrategyError


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
    "atr14_pct",
    "volatility_20d",
    "range_pct",
    "gap_pct",
    "close_pct_of_20d_range",
    "close_pct_of_60d_range",
    "distance_to_20d_high",
    "distance_to_20d_low",
    "position_return",
    "holding_days",
    "position_ratio",
    "days_since_last_trade",
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
    "ema": 2,
    "pct_slope": 2,
    "zscore": 2,
    "percentile_rank": 2,
    "drawdown_from_high": 2,
}
WINDOW_FUNCTIONS = {"sum", "avg", "std", "highest", "lowest", "ema", "pct_slope", "zscore", "percentile_rank", "drawdown_from_high"}
CHANGE_FUNCTIONS = {"change", "pct_change"}
INDICATOR_WARMUP_BARS = 180
MIN_ANNUALIZATION_PERIODS = 60
DEFAULT_CONFLICT_POLICY = "exit_first"
CONFLICT_POLICY_VALUES = {"exit_first", "entry_first", "allow_reentry", "skip"}


def _validate_strategy_config(strategy_config: dict) -> None:
    risk = strategy_config.get("risk")
    entry_rules = _normalize_strategy_rules(strategy_config, "entry")
    exit_rules = _normalize_strategy_rules(strategy_config, "exit")
    if not isinstance(risk, dict):
        raise StrategyError("规则配置缺少买入规则、卖出规则或风控参数。")
    _normalize_conflict_policy(strategy_config, strict=True)
    _validate_ordered_rules(entry_rules, "买入规则", "buy")
    _validate_ordered_rules(exit_rules, "卖出规则", "sell")


def _normalize_conflict_policy(strategy_config: dict, *, strict: bool = False) -> str:
    risk = strategy_config.get("risk") or {}
    policy = str(risk.get("conflictPolicy") or DEFAULT_CONFLICT_POLICY).strip()
    if policy in CONFLICT_POLICY_VALUES:
        return policy
    if strict:
        raise StrategyError("信号冲突处理方式无效。")
    return DEFAULT_CONFLICT_POLICY


def _normalize_strategy_rules(strategy_config: dict, scope: str) -> list[dict]:
    rules_key = "entryRules" if scope == "entry" else "exitRules"
    legacy_key = "entry" if scope == "entry" else "exit"
    action_type = "buy" if scope == "entry" else "sell"

    rules = strategy_config.get(rules_key)
    if isinstance(rules, list) and rules:
        return rules

    legacy_group = strategy_config.get(legacy_key)
    if isinstance(legacy_group, dict):
        return [
            {
                "id": f"{scope}_legacy",
                "name": "买入规则" if scope == "entry" else "卖出规则",
                "action": {"type": action_type, "size": 1.0},
                "conditions": legacy_group,
            }
        ]
    return []


def _validate_ordered_rules(rules: list[dict], label: str, action_type: str) -> None:
    if not isinstance(rules, list) or not rules:
        raise StrategyError(f"{label}不能为空。")
    for index, rule in enumerate(rules, start=1):
        if not isinstance(rule, dict):
            raise StrategyError(f"{label}第 {index} 条规则格式无效。")
        conditions = rule.get("conditions")
        action = rule.get("action")
        if not isinstance(conditions, dict) or not isinstance(action, dict):
            raise StrategyError(f"{label}第 {index} 条规则缺少条件或动作。")
        if action.get("type") != action_type:
            raise StrategyError(f"{label}第 {index} 条规则动作类型无效。")
        size = _parse_number_token(action.get("size"), f"{label}第 {index} 条规则仓位")
        if size <= 0 or size > 1:
            raise StrategyError(f"{label}第 {index} 条规则仓位必须大于 0 且不超过 100%。")
        _validate_rule_group(conditions, f"{label}第 {index} 条规则")


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
            if token.get("value") in {"+", "-"} and previous_kind in {None, "operator", "groupStart"}:
                current_kind = "unaryOperator"
                previous_kind = current_kind
                continue
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
    if previous_kind in {"operator", "groupStart", "unaryOperator"}:
        raise StrategyError(f"{label}结尾缺少值。")


def _validate_variable_token(token: dict, label: str) -> None:
    name = token.get("name")
    if name not in RULE_FIELD_VALUES:
        raise StrategyError(f"{label}不支持：{name}。")
    try:
        offset = int(token.get("offset") or 0)
    except (TypeError, ValueError) as exc:
        raise StrategyError(f"{label}历史引用偏移格式无效。") from exc
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
