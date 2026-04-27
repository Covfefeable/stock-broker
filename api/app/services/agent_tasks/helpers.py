from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from app.models.agent_iteration import AgentIteration
from app.models.agent_task import AgentTask
from app.models.index_asset import IndexAsset
from app.models.stock import Stock
from app.models.user import User
from app.services.agent.labels import _agent_intent_label, _agent_mode_label
from app.services.agent.strategy_description import _describe_rule_list
from app.services.agent_tasks.errors import AgentTaskError
from app.services.scoring import calculate_performance_score
from app.services.settings import get_or_create_settings


def _resolve_ai_model(user: User, value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise AgentTaskError("请选择 AI 模型。")

    model_name = str(value.get("name", "")).strip()
    model = str(value.get("model", "")).strip()
    base_url = str(value.get("baseUrl", "")).strip()
    api_key = str(value.get("apiKey", "")).strip()

    if not model_name or not model or not base_url or not api_key:
        raise AgentTaskError("所选 AI 模型配置不完整，请先在系统设置中补齐。")

    settings = get_or_create_settings(user)
    matched = next(
        (
            row
            for row in settings.ai_models
            if str(row.get("name", "")).strip() == model_name
            and str(row.get("model", "")).strip() == model
            and str(row.get("baseUrl", "")).strip() == base_url
            and str(row.get("apiKey", "")).strip() == api_key
        ),
        None,
    )
    if not matched:
        raise AgentTaskError("所选 AI 模型不存在或已变更，请重新选择。")

    return {
        "name": model_name,
        "model": model,
        "baseUrl": base_url,
        "apiKey": api_key,
    }


def _resolve_asset_name(country_code: str, asset_type: str, asset_identifier: str) -> str:
    if asset_type == "stock":
        if ":" not in asset_identifier:
            raise AgentTaskError("股票标的格式无效。")
        exchange_code, ticker = asset_identifier.split(":", 1)
        row = Stock.query.filter_by(exchange_code=exchange_code, ticker=ticker).first()
        if not row:
            raise AgentTaskError("未找到对应股票，请先同步股票清单。")
        return row.name

    row = IndexAsset.query.filter_by(country_code=country_code, ticker=asset_identifier).first()
    if not row:
        raise AgentTaskError("未找到对应指数，请先同步指数清单。")
    return row.name


def _build_agent_research_state(
    task: AgentTask,
    iteration: int,
    iteration_results: list[dict],
    best_result: dict | None,
    benchmark_metrics: dict[str, float],
) -> dict:
    del iteration_results, best_result, benchmark_metrics
    return {
        "iteration": iteration,
        "maxIterations": task.max_iterations,
    }


def _score_result(result: dict, *, weights: dict[str, float] | None = None) -> float:
    return calculate_performance_score(
        result.get("annualReturn"),
        result.get("sharpe"),
        result.get("maxDrawdown"),
        weights=weights,
    )


def _enrich_agent_thoughts(
    analysis: str,
    action_plan: str,
    generation_result: dict,
    research_state: dict,
) -> tuple[str, str]:
    mode = generation_result.get("mode") or "explore_new"
    intent = generation_result.get("intent") or "trend_following"
    analysis_parts = [
        f"本轮模式：{_agent_mode_label(mode)}。",
        f"交易风格：{_agent_intent_label(intent)}。",
        analysis.strip(),
    ]

    action_parts = [action_plan.strip()]
    if research_state.get("stagnationRounds"):
        action_parts.append(f"当前已停滞 {research_state['stagnationRounds']} 轮。")

    return "".join(analysis_parts), "".join(action_parts)


def _parse_decimal(value: Any, field_label: str) -> Decimal:
    if value in (None, ""):
        raise AgentTaskError(f"请填写{field_label}。")
    try:
        return Decimal(str(value))
    except Exception as exc:  # noqa: BLE001
        raise AgentTaskError(f"{field_label}格式无效。") from exc


def _parse_int(value: Any, field_label: str) -> int:
    if value in (None, ""):
        raise AgentTaskError(f"请填写{field_label}。")
    try:
        return int(value)
    except Exception as exc:  # noqa: BLE001
        raise AgentTaskError(f"{field_label}格式无效。") from exc


def _parse_date(value: Any, field_label: str) -> date:
    if not value:
        raise AgentTaskError(f"请填写{field_label}。")
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise AgentTaskError(f"{field_label}格式无效。") from exc


def _is_better_result(current: dict, best: dict | None, *, weights: dict[str, float] | None = None) -> bool:
    if best is None:
        return True
    return _score_result(current, weights=weights) > _score_result(best, weights=weights)


def _build_iteration_summary(
    task: AgentTask,
    iteration: int,
    strategy_config: dict,
    preview: dict,
    previous_best: dict | None,
    benchmark_metrics: dict[str, float],
    analysis: str | None = None,
    action_plan: str | None = None,
    mode: str | None = None,
    intent: str | None = None,
    score_weights: dict[str, float] | None = None,
) -> str:
    entry_desc = _describe_rule_list(strategy_config, "entry")
    exit_desc = _describe_rule_list(strategy_config, "exit")

    summary_parts = [
        f"本轮模式：{_agent_mode_label(mode)}。",
        f"交易风格：{_agent_intent_label(intent)}。",
        f"本轮买入规则为“{entry_desc}”，卖出规则为“{exit_desc}”。",
        f"回测结果：年化收益 {preview['annualReturn']:.2f}% ，最大回撤 {preview['maxDrawdown']:.2f}% ，Sharpe {preview['sharpe']:.2f}。",
        f"买入持有基准：年化收益 {benchmark_metrics['benchmarkAnnualReturn']:.2f}% ，总收益 {benchmark_metrics['benchmarkReturn']:.2f}% 。",
    ]

    if analysis:
        summary_parts.append(f"模型分析：{analysis}")
    if action_plan:
        summary_parts.append(f"本轮决策：{action_plan}")

    if previous_best is None or _is_better_result(preview, previous_best, weights=score_weights):
        summary_parts.append("这一轮刷新了当前最优结果，后续可以围绕这组条件继续微调。")
    else:
        summary_parts.append("这一轮没有超过当前最优结果，下一轮可以尝试调整买入阈值或收紧退出条件。")

    if preview["annualReturn"] < float(task.target_annual_return):
        summary_parts.append("收益仍未达到目标年化收益率。")
    if preview["maxDrawdown"] > float(task.max_drawdown_limit):
        summary_parts.append("最大回撤仍高于设定上限。")
    if preview["sharpe"] < float(task.min_sharpe):
        summary_parts.append("Sharpe 仍低于目标。")

    return "".join(summary_parts)


def _build_analysis_fallback(task: AgentTask, preview: dict, benchmark_metrics: dict[str, float]) -> str:
    parts = [
        f"当前策略年化收益 {preview['annualReturn']:.2f}% ，Sharpe {preview['sharpe']:.2f}，最大回撤 {preview['maxDrawdown']:.2f}%。",
        f"买入持有基准年化收益 {benchmark_metrics['benchmarkAnnualReturn']:.2f}% ，最大回撤 {benchmark_metrics['benchmarkMaxDrawdown']:.2f}%。",
    ]
    if preview["annualReturn"] >= benchmark_metrics["benchmarkAnnualReturn"]:
        parts.append("当前策略在收益层面已达到或超过买入持有基准。")
    else:
        parts.append("当前策略在收益层面仍弱于买入持有基准。")
    if preview["maxDrawdown"] <= benchmark_metrics["benchmarkMaxDrawdown"]:
        parts.append("但它在回撤控制上更占优。")
    return "".join(parts)


def _build_action_plan_fallback(strategy_config: dict, preview: dict, benchmark_metrics: dict[str, float]) -> str:
    entry_desc = _describe_rule_list(strategy_config, "entry")
    exit_desc = _describe_rule_list(strategy_config, "exit")
    if preview["annualReturn"] < benchmark_metrics["benchmarkAnnualReturn"]:
        return f"继续调整当前策略，重点优化买入“{entry_desc}”和卖出“{exit_desc}”的阈值，争取先超过买入持有基准。"
    return f"保留当前“{entry_desc} / {exit_desc}”的核心思路，再围绕回撤和 Sharpe 做微调。"


def _build_noop_strategy_config(task: AgentTask) -> dict:
    return {
        "entry": {
            "type": "group",
            "logic": "and",
            "children": [
                {
                    "type": "condition",
                    "leftExpression": [{"type": "variable", "name": "close"}],
                    "operator": ">",
                    "rightExpression": [{"type": "number", "value": 999999999}],
                }
            ],
        },
        "exit": {
            "type": "group",
            "logic": "and",
            "children": [
                {
                    "type": "condition",
                    "leftExpression": [{"type": "variable", "name": "close"}],
                    "operator": "<",
                    "rightExpression": [{"type": "number", "value": -1}],
                }
            ],
        },
        "risk": {
            "backtestStartDate": task.backtest_start_date.isoformat(),
            "backtestEndDate": task.backtest_end_date.isoformat(),
        },
    }


def _score_iteration(iteration: AgentIteration | None, *, weights: dict[str, float] | None = None) -> float | None:
    if not iteration:
        return None
    return round(
        _score_result(
            {
                "annualReturn": float(iteration.annual_return) if iteration.annual_return is not None else 0,
                "sharpe": float(iteration.sharpe) if iteration.sharpe is not None else 0,
                "maxDrawdown": float(iteration.max_drawdown) if iteration.max_drawdown is not None else 0,
            },
            weights=weights,
        ),
        2,
    )


def _get_best_iteration(task: AgentTask, *, score_weights: dict[str, float] | None = None) -> AgentIteration | None:
    iterations = AgentIteration.query.filter(AgentIteration.task_id == task.id).all()
    if not iterations:
        return None

    def sort_key(iteration: AgentIteration) -> tuple[float, int, int]:
        score = _score_iteration(iteration, weights=score_weights)
        return (
            score if score is not None else float("-inf"),
            iteration.iteration_number,
            iteration.id,
        )

    return max(
        iterations,
        key=sort_key,
    )


def list_available_ai_models(user: User) -> list[dict[str, str]]:
    settings = get_or_create_settings(user)
    models = settings.ai_models or []
    return [
        {
            "label": row.get("name") or row.get("model") or "未命名模型",
            "value": str(index),
            "name": row.get("name", ""),
            "model": row.get("model", ""),
            "baseUrl": row.get("baseUrl", ""),
            "apiKey": row.get("apiKey", ""),
        }
        for index, row in enumerate(models)
        if any(str(row.get(key, "")).strip() for key in ("name", "model", "baseUrl", "apiKey"))
    ]
