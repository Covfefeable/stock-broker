from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import desc, or_

from app.extensions import db
from app.models.etf import Etf
from app.models.etf_daily_bar import EtfDailyBar
from app.models.index_asset import IndexAsset
from app.models.index_daily_bar import IndexDailyBar
from app.models.stock import Stock
from app.models.stock_daily_bar import StockDailyBar
from app.models.strategy import Strategy
from app.models.strategy_evaluation import StrategyEvaluation
from app.models.user import User
from app.services.market_data import apply_stock_split_adjustments
from app.services.agent.strategy_description import _describe_group
from app.services.strategies.dsl import _normalize_conflict_policy, _normalize_strategy_rules
from app.services.strategies.expression import _evaluate_group
from app.services.strategies.indicators import _calculate_indicators


class TradeDecisionError(Exception):
    pass


@dataclass(frozen=True)
class DecisionAsset:
    asset_type: str
    country_code: str
    asset_identifier: str
    ticker: str
    name: str
    exchange_code: str | None = None


def evaluate_trade_decision(user: User, payload: dict) -> dict:
    asset = _parse_asset(payload)
    position = _parse_position(payload.get("position") or {})
    extra_strategy_ids = _parse_extra_strategy_ids(payload.get("extraStrategyIds"))
    bars = _load_decision_bars(asset)
    if len(bars) < 2:
        raise TradeDecisionError("当前标的没有足够的历史日线数据，无法生成操作建议。")

    rows = _load_strategy_rows(user, asset, extra_strategy_ids)
    items = [
        _evaluate_strategy_row(strategy, evaluation, asset, bars, position)
        for strategy, evaluation in rows
    ]
    items.sort(key=lambda item: (item["evaluationScore"], item["updatedAt"] or ""), reverse=True)

    return {
        "asset": {
            "assetType": asset.asset_type,
            "countryCode": asset.country_code,
            "exchangeCode": asset.exchange_code,
            "ticker": asset.ticker,
            "name": asset.name,
            "assetIdentifier": asset.asset_identifier,
            "latestDate": bars[-1]["date"].isoformat() if bars else None,
        },
        "position": {
            "status": position["status"],
            "ratio": position["ratio"],
            "floatingReturn": position["floatingReturn"],
            "holdingDays": position["holdingDays"],
        },
        "summary": _build_summary(items),
        "items": items,
        "filtered": {
            "eligibleCount": len(items),
            "extraStrategyCount": len(extra_strategy_ids),
        },
    }


def list_eligible_extra_strategies(
    user: User,
    *,
    keyword: str = "",
    exclude_asset_type: str = "",
    exclude_asset_identifier: str = "",
) -> dict:
    query = _eligible_strategy_query(user)
    normalized_keyword = keyword.strip()
    if normalized_keyword:
        pattern = f"%{normalized_keyword}%"
        query = query.filter(
            or_(
                Strategy.name.ilike(pattern),
                Strategy.asset_name.ilike(pattern),
                Strategy.asset_identifier.ilike(pattern),
            )
        )
    if exclude_asset_type and exclude_asset_identifier:
        query = query.filter(
            ~(
                (Strategy.asset_type == exclude_asset_type)
                & (Strategy.asset_identifier == exclude_asset_identifier)
            )
        )
    rows = query.order_by(desc(StrategyEvaluation.score).nullslast(), desc(Strategy.updated_at)).limit(200).all()
    return {
        "items": [
            {
                "label": f"{strategy.name} / {strategy.asset_name or strategy.asset_identifier} / 评分 {float(evaluation.score):.2f}",
                "value": strategy.id,
                "strategyId": strategy.id,
                "name": strategy.name,
                "assetType": strategy.asset_type,
                "assetName": strategy.asset_name,
                "assetIdentifier": strategy.asset_identifier,
                "evaluationScore": _metric(evaluation.score),
            }
            for strategy, evaluation in rows
        ]
    }


def _parse_asset(payload: dict) -> DecisionAsset:
    asset_type = str(payload.get("assetType") or "").strip()
    country_code = str(payload.get("countryCode") or "").strip().upper()
    ticker = str(payload.get("ticker") or "").strip()
    exchange_code = str(payload.get("exchangeCode") or "").strip().upper()
    if asset_type not in {"stock", "etf", "index"}:
        raise TradeDecisionError("请选择股票、ETF或指数。")
    if not country_code:
        raise TradeDecisionError("请选择国家/地区。")
    if not ticker:
        raise TradeDecisionError("请选择标的。")

    if asset_type in {"stock", "etf"}:
        if not exchange_code:
            raise TradeDecisionError("请选择交易所。")
        model = Stock if asset_type == "stock" else Etf
        asset = model.query.filter(
            model.exchange_code == exchange_code,
            model.ticker == ticker,
            model.country_code == country_code,
        ).first()
        if not asset:
            raise TradeDecisionError(f"未找到对应{'股票' if asset_type == 'stock' else 'ETF'}。")
        return DecisionAsset(
            asset_type=asset_type,
            country_code=asset.country_code,
            exchange_code=asset.exchange_code,
            ticker=asset.ticker,
            name=asset.name,
            asset_identifier=f"{asset.exchange_code}:{asset.ticker}",
        )

    index_asset = IndexAsset.query.filter(
        IndexAsset.country_code == country_code,
        IndexAsset.ticker == ticker,
    ).first()
    if not index_asset:
        raise TradeDecisionError("未找到对应指数。")
    return DecisionAsset(
        asset_type="index",
        country_code=index_asset.country_code,
        ticker=index_asset.ticker,
        name=index_asset.name,
        asset_identifier=index_asset.ticker,
    )


def _parse_position(raw: dict) -> dict:
    status = str(raw.get("status") or "empty").strip()
    if status not in {"empty", "holding"}:
        raise TradeDecisionError("当前仓位状态无效。")
    ratio = _normalize_ratio(_to_float(raw.get("ratio"), 0.0))
    floating_return = _normalize_optional_ratio(_to_optional_float(raw.get("floatingReturn")))
    holding_days = _to_optional_int(raw.get("holdingDays"))
    if status == "empty":
        return {"status": "empty", "ratio": 0.0, "floatingReturn": None, "holdingDays": None}
    if ratio <= 0 or ratio > 1:
        raise TradeDecisionError("当前仓位比例必须大于 0 且不超过 100%。")
    return {
        "status": "holding",
        "ratio": ratio,
        "floatingReturn": floating_return,
        "holdingDays": holding_days,
    }


def _parse_extra_strategy_ids(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    result: list[int] = []
    for item in value:
        try:
            strategy_id = int(item)
        except (TypeError, ValueError):
            continue
        if strategy_id > 0 and strategy_id not in result:
            result.append(strategy_id)
    return result


def _eligible_strategy_query(user: User):
    return (
        db.session.query(Strategy, StrategyEvaluation)
        .join(
            StrategyEvaluation,
            (StrategyEvaluation.strategy_id == Strategy.id)
            & (StrategyEvaluation.user_id == user.id),
        )
        .filter(
            Strategy.user_id == user.id,
            Strategy.archived_at.is_(None),
            StrategyEvaluation.status == "success",
            StrategyEvaluation.score.isnot(None),
        )
    )


def _load_strategy_rows(user: User, asset: DecisionAsset, extra_strategy_ids: list[int]) -> list[tuple[Strategy, StrategyEvaluation]]:
    query = _eligible_strategy_query(user).filter(
        Strategy.asset_type == asset.asset_type,
        Strategy.asset_identifier == asset.asset_identifier,
        Strategy.country_region == asset.country_code,
    )
    rows = query.all()
    if extra_strategy_ids:
        extra_rows = _eligible_strategy_query(user).filter(Strategy.id.in_(extra_strategy_ids)).all()
        existing_ids = {strategy.id for strategy, _ in rows}
        rows.extend((strategy, evaluation) for strategy, evaluation in extra_rows if strategy.id not in existing_ids)
    return rows


def _load_decision_bars(asset: DecisionAsset) -> list[dict]:
    if asset.asset_type in {"stock", "etf"}:
        daily_model = StockDailyBar if asset.asset_type == "stock" else EtfDailyBar
        rows = (
            daily_model.query.filter(
                daily_model.exchange_code == asset.exchange_code,
                daily_model.ticker == asset.ticker,
            )
            .order_by(daily_model.trade_date.asc(), daily_model.id.asc())
            .all()
        )
        bars = [_bar_to_dict(row) for row in rows]
        if asset.asset_type == "stock":
            return apply_stock_split_adjustments(bars, asset.exchange_code or "", asset.ticker)
        return bars

    rows = (
        IndexDailyBar.query.filter(
            IndexDailyBar.country_code == asset.country_code,
            IndexDailyBar.ticker == asset.ticker,
        )
        .order_by(IndexDailyBar.trade_date.asc(), IndexDailyBar.id.asc())
        .all()
    )
    return [_bar_to_dict(row) for row in rows]


def _bar_to_dict(row) -> dict:
    return {
        "date": row.trade_date,
        "open": _to_optional_float(row.open),
        "high": _to_optional_float(row.high),
        "low": _to_optional_float(row.low),
        "close": _to_optional_float(row.close),
        "volume": _to_optional_float(row.volume),
        "isWarmup": False,
    }


def _evaluate_strategy_row(
    strategy: Strategy,
    evaluation: StrategyEvaluation,
    asset: DecisionAsset,
    bars: list[dict],
    position: dict,
) -> dict:
    contexts = _build_latest_contexts(bars, position)
    current_index = len(contexts) - 1
    strategy_config = strategy.strategy_config or {}
    entry_rules = _normalize_strategy_rules(strategy_config, "entry")
    exit_rules = _normalize_strategy_rules(strategy_config, "exit")
    conflict_policy = _normalize_conflict_policy(strategy_config)
    position_ratio = float(position["ratio"] or 0.0)

    triggered_exit_rule = _find_triggered_rule(exit_rules, contexts, current_index) if position_ratio > 0 else None
    triggered_entry_rule = _find_triggered_rule(entry_rules, contexts, current_index) if position_ratio < 1 else None
    triggered_entry_rule, triggered_exit_rule = _resolve_signal_conflict(
        triggered_entry_rule,
        triggered_exit_rule,
        conflict_policy,
    )

    recommendation = _build_recommendation(
        triggered_entry_rule=triggered_entry_rule,
        triggered_exit_rule=triggered_exit_rule,
        position_ratio=position_ratio,
    )
    report = evaluation.report or {}
    full_original = report.get("fullOriginal") or {}
    is_same_asset = strategy.asset_type == asset.asset_type and strategy.asset_identifier == asset.asset_identifier

    return {
        "strategyId": strategy.id,
        "strategyName": strategy.name,
        "strategyAssetName": strategy.asset_name,
        "strategyAssetIdentifier": strategy.asset_identifier,
        "strategyAssetType": strategy.asset_type,
        "isSameAsset": is_same_asset,
        "evaluationScore": _metric(evaluation.score),
        "evaluationConclusion": evaluation.conclusion,
        "annualReturn": _metric(full_original.get("annualReturn")),
        "maxDrawdown": _metric(full_original.get("maxDrawdown")),
        "sharpe": _metric(full_original.get("sharpe")),
        "recommendation": recommendation,
        "signalDate": bars[-1]["date"].isoformat(),
        "updatedAt": strategy.updated_at.isoformat() if strategy.updated_at else None,
    }


def _build_latest_contexts(bars: list[dict], position: dict) -> list[dict]:
    indicators = _calculate_indicators(bars)
    contexts: list[dict] = []
    for index, bar in enumerate(bars):
        context = {
            **bar,
            **{name: series[index] for name, series in indicators.items()},
            "position_ratio": 0.0,
            "position_return": None,
            "holding_days": None,
            "days_since_last_trade": None,
        }
        contexts.append(context)
    contexts[-1]["position_ratio"] = float(position["ratio"] or 0.0)
    contexts[-1]["position_return"] = position.get("floatingReturn")
    contexts[-1]["holding_days"] = position.get("holdingDays")
    return contexts


def _find_triggered_rule(rules: list[dict], contexts: list[dict], current_index: int) -> dict | None:
    for rule in rules:
        conditions = rule.get("conditions") or {}
        if _evaluate_group(conditions, contexts, current_index):
            return rule
    return None


def _resolve_signal_conflict(
    triggered_entry_rule: dict | None,
    triggered_exit_rule: dict | None,
    conflict_policy: str,
) -> tuple[dict | None, dict | None]:
    if not triggered_entry_rule or not triggered_exit_rule:
        return triggered_entry_rule, triggered_exit_rule
    if conflict_policy == "entry_first":
        return triggered_entry_rule, None
    if conflict_policy == "allow_reentry":
        return triggered_entry_rule, triggered_exit_rule
    if conflict_policy == "skip":
        return None, None
    return None, triggered_exit_rule


def _build_recommendation(
    *,
    triggered_entry_rule: dict | None,
    triggered_exit_rule: dict | None,
    position_ratio: float,
) -> dict:
    if triggered_entry_rule and triggered_exit_rule:
        sell_size = _rule_size(triggered_exit_rule, 1.0)
        buy_size = _rule_size(triggered_entry_rule, 0.0)
        sell_ratio = min(position_ratio, sell_size)
        buy_ratio = min(max(1.0 - max(position_ratio - sell_ratio, 0.0), 0.0), buy_size)
        return {
            "action": "rebalance",
            "label": f"先卖 {sell_ratio * 100:.0f}% 再买 {buy_ratio * 100:.0f}%",
            "size": round(buy_ratio - sell_ratio, 4),
            "ruleName": f"{_rule_name(triggered_exit_rule)} / {_rule_name(triggered_entry_rule)}",
            "reason": "买卖信号同时触发，按策略设置先卖出再买入。",
            "ruleDetail": f"卖出：{_rule_detail(triggered_exit_rule)}；买入：{_rule_detail(triggered_entry_rule)}",
        }
    if triggered_exit_rule:
        size = _rule_size(triggered_exit_rule, 1.0)
        sell_ratio = min(position_ratio, size)
        action = "sell" if sell_ratio >= position_ratio else "reduce"
        rule_detail = _rule_detail(triggered_exit_rule)
        return {
            "action": action,
            "label": f"{'卖出' if action == 'sell' else '减仓'} {sell_ratio * 100:.0f}%",
            "size": round(sell_ratio, 4),
            "ruleName": _rule_name(triggered_exit_rule),
            "reason": f"{_rule_name(triggered_exit_rule)}触发",
            "ruleDetail": rule_detail,
        }
    if triggered_entry_rule:
        size = _rule_size(triggered_entry_rule, 0.0)
        buy_ratio = min(max(1.0 - position_ratio, 0.0), size)
        rule_detail = _rule_detail(triggered_entry_rule)
        if buy_ratio <= 0:
            return {
                "action": "hold" if position_ratio > 0 else "watch",
                "label": "继续持有" if position_ratio > 0 else "继续观望",
                "size": 0.0,
                "ruleName": _rule_name(triggered_entry_rule),
                "reason": "买入规则触发，但当前仓位已满。",
                "ruleDetail": rule_detail,
            }
        action = "buy" if position_ratio <= 0 else "add"
        return {
            "action": action,
            "label": f"{'买入' if action == 'buy' else '加仓'} {buy_ratio * 100:.0f}%",
            "size": round(buy_ratio, 4),
            "ruleName": _rule_name(triggered_entry_rule),
            "reason": f"{_rule_name(triggered_entry_rule)}触发",
            "ruleDetail": rule_detail,
        }
    return {
        "action": "hold" if position_ratio > 0 else "watch",
        "label": "继续持有" if position_ratio > 0 else "继续观望",
        "size": 0.0,
        "ruleName": None,
        "reason": "当前未触发可执行规则。",
        "ruleDetail": None,
    }


def _build_summary(items: list[dict]) -> dict:
    if not items:
        return {
            "label": "暂无可用策略",
            "description": "没有找到该标的下非归档且已在回测实验室成功评估的策略。",
            "counts": {"buy": 0, "sell": 0, "hold": 0, "watch": 0, "rebalance": 0},
        }
    counts = {"buy": 0, "sell": 0, "hold": 0, "watch": 0, "rebalance": 0}
    weighted_score = 0.0
    total_weight = 0.0
    for item in items:
        action = item["recommendation"]["action"]
        if action in {"buy", "add"}:
            counts["buy"] += 1
            direction = 1
        elif action in {"sell", "reduce"}:
            counts["sell"] += 1
            direction = -1
        elif action == "hold":
            counts["hold"] += 1
            direction = 0
        elif action == "rebalance":
            counts["rebalance"] += 1
            direction = 0
        else:
            counts["watch"] += 1
            direction = 0
        weight = max(float(item["evaluationScore"] or 0), 1.0)
        weighted_score += direction * weight
        total_weight += weight

    signal = weighted_score / total_weight if total_weight else 0
    if signal >= 0.25:
        label = "偏买入"
    elif signal <= -0.25:
        label = "偏卖出"
    elif counts["hold"] > counts["watch"]:
        label = "偏持有"
    else:
        label = "偏观望"
    return {
        "label": label,
        "description": (
            f"本次共纳入 {len(items)} 个已评估策略，其中 {counts['buy']} 个建议买入/加仓，"
            f"{counts['sell']} 个建议卖出/减仓，{counts['rebalance']} 个建议先卖再买，"
            f"{counts['hold']} 个建议持有，{counts['watch']} 个建议观望。"
        ),
        "counts": counts,
    }


def _rule_size(rule: dict, fallback: float) -> float:
    try:
        return max(min(float((rule.get("action") or {}).get("size", fallback)), 1.0), 0.0)
    except (TypeError, ValueError):
        return fallback


def _rule_name(rule: dict) -> str:
    return str(rule.get("name") or "规则")


def _rule_detail(rule: dict | None) -> str | None:
    if not rule:
        return None
    action = rule.get("action") or {}
    action_type = action.get("type")
    action_label = "买入" if action_type == "buy" else "卖出"
    size = _rule_size(rule, 1.0)
    conditions_text = _describe_group(rule.get("conditions") or {})
    return f"{_rule_name(rule)}（{action_label} {size * 100:.0f}%）：{conditions_text}"


def _to_float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _to_optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise TradeDecisionError("数值格式无效。") from exc


def _to_optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise TradeDecisionError("持有交易日数格式无效。") from exc
    return max(number, 0)


def _normalize_ratio(value: float) -> float:
    if value > 1:
        return value / 100
    return value


def _normalize_optional_ratio(value: float | None) -> float | None:
    if value is None:
        return None
    if abs(value) > 1:
        return value / 100
    return value


def _metric(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None
