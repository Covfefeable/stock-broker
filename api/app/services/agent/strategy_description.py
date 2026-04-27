from __future__ import annotations

from app.services.agent.rule_definitions import FIELD_LABELS_BY_VALUE, OPERATOR_LABELS


def _describe_rule_list(strategy_config: dict, scope: str) -> str:
    rules_key = "entryRules" if scope == "entry" else "exitRules"
    legacy_key = "entry" if scope == "entry" else "exit"
    rules = strategy_config.get(rules_key)
    if not isinstance(rules, list) or not rules:
        legacy_group = strategy_config.get(legacy_key)
        return _describe_group(legacy_group) if isinstance(legacy_group, dict) else "未配置"
    parts: list[str] = []
    for index, rule in enumerate(rules, start=1):
        action = rule.get("action") or {}
        action_label = "买入" if action.get("type") == "buy" else "卖出"
        try:
            size_label = f"{float(action.get('size') or 0) * 100:g}%"
        except (TypeError, ValueError):
            size_label = "-"
        name = str(rule.get("name") or f"规则 {index}").strip()
        parts.append(f"{index}. {name}（{action_label}{size_label}）：{_describe_group(rule.get('conditions') or {})}")
    return "；".join(parts)


def _describe_group(group: dict) -> str:
    children = group.get("children") or []
    if not children:
        return "未配置"
    joiner = "且" if group.get("logic") == "and" else "或"
    parts: list[str] = []
    for child in children:
        if child.get("type") == "group":
            parts.append(f"（{_describe_group(child)}）")
        else:
            parts.append(_describe_condition(child))
    return joiner.join(parts)


def _describe_condition(condition: dict) -> str:
    left = _describe_expression(condition.get("leftExpression") or [])
    operator = OPERATOR_LABELS.get(condition.get("operator"), condition.get("operator") or "")
    right = _describe_expression(condition.get("rightExpression") or [])
    return f"{left}{operator}{right}"


def _describe_expression(tokens: list[dict]) -> str:
    parts: list[str] = []
    for token in tokens:
        token_type = token.get("type")
        if token_type == "variable":
            label = FIELD_LABELS_BY_VALUE.get(token.get("name"), token.get("name") or "")
            offset = int(token.get("offset") or 0)
            parts.append(f"{label}[{offset}]" if offset else label)
        elif token_type == "number":
            parts.append(str(token.get("value")))
        elif token_type == "operator":
            parts.append(str(token.get("value")))
        elif token_type == "groupStart":
            parts.append("(")
        elif token_type == "groupEnd":
            parts.append(")")
        elif token_type == "function":
            args = token.get("args") or []
            parts.append(f"{token.get('name')}({', '.join(_describe_expression(arg) for arg in args)})")
    return " ".join(parts) if parts else "-"


