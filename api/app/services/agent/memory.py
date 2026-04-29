from __future__ import annotations

import json

from app.models.agent_iteration import AgentIteration
from app.models.agent_task import AgentTask
from app.services.agent.curve_diagnostics import _format_curve_diagnostics_for_memory
from app.services.agent.labels import _agent_intent_label, _agent_mode_label
from app.services.agent.strategy_description import _describe_rule_list
from app.services.agent.time_robustness import _format_time_robustness_for_memory
from app.services.scoring import calculate_performance_score


AGENT_RECENT_PROMPT_MEMORY_LIMIT = 10
AGENT_BEST_PROMPT_MEMORY_LIMIT = 3


def _score_result(result: dict, *, weights: dict[str, float] | None = None) -> float:
    return calculate_performance_score(
        result.get("annualReturn"),
        result.get("sharpe"),
        result.get("maxDrawdown"),
        weights=weights,
    )


def _select_agent_prompt_memories(iteration_memory_rows: list[dict]) -> dict[str, list[str]]:
    best_rows = sorted(
        iteration_memory_rows,
        key=lambda item: float(item.get("score") or float("-inf")),
        reverse=True,
    )[:AGENT_BEST_PROMPT_MEMORY_LIMIT]
    recent_rows = iteration_memory_rows[-AGENT_RECENT_PROMPT_MEMORY_LIMIT:]
    return {
        "best": [_format_agent_memory_item(item) for item in best_rows if item.get("memory")],
        "recent": [_format_agent_memory_item(item) for item in recent_rows if item.get("memory")],
    }


def _format_agent_memory_item(item: dict) -> str:
    memory = str(item.get("memory") or "")
    try:
        payload = json.loads(memory)
    except json.JSONDecodeError:
        return f"第 {item.get('iteration', '-')} 轮：{memory}"

    metrics = payload.get("metrics") or {}
    strategy_digest = payload.get("strategyDigest") or {}
    diagnostics_text = _format_curve_diagnostics_for_memory(payload.get("curveDiagnostics") or {})
    time_robustness_text = _format_time_robustness_for_memory(payload.get("timeRobustness") or {})
    return (
        f"第 {payload.get('round', item.get('iteration', '-'))} 轮："
        f"score={payload.get('score', '-')}，"
        f"benchmarkScore={payload.get('benchmarkScore', '-')}，"
        f"scoreDiff={payload.get('scoreDiff', '-')}，"
        f"年化={metrics.get('annualReturn', '-')}%，"
        f"回撤={metrics.get('maxDrawdown', '-')}%，"
        f"Sharpe={metrics.get('sharpe', '-')}，"
        f"交易={metrics.get('tradeCount', '-')} 次，"
        f"模式={payload.get('modeLabel', payload.get('mode', '-'))}，"
        f"交易风格={payload.get('intentLabel', payload.get('intent', '-'))}。\n"
        f"  买入：{strategy_digest.get('entry', '-')}\n"
        f"  卖出：{strategy_digest.get('exit', '-')}\n"
        f"  曲线诊断：{diagnostics_text}\n"
        f"  跨时间验证：{time_robustness_text}"
    )



def _build_iteration_memory(
    iteration: int,
    strategy_config: dict,
    preview: dict,
    benchmark_metrics: dict[str, float],
    analysis: str,
    action_plan: str,
    summary: str,
    generation_result: dict,
    research_state: dict,
    curve_diagnostics: dict,
    time_robustness: dict,
    score_weights: dict[str, float] | None = None,
) -> str:
    del summary, research_state
    mode = generation_result.get("mode") or "explore_new"
    intent = generation_result.get("intent") or "trend_following"
    strategy_score = _score_result(preview, weights=score_weights)
    benchmark_score = calculate_performance_score(
        benchmark_metrics.get("benchmarkAnnualReturn"),
        benchmark_metrics.get("benchmarkSharpe"),
        benchmark_metrics.get("benchmarkMaxDrawdown"),
        weights=score_weights,
    )
    memory_payload = {
        "round": iteration,
        "mode": mode,
        "modeLabel": _agent_mode_label(mode),
        "intent": intent,
        "intentLabel": _agent_intent_label(intent),
        "score": round(strategy_score, 2),
        "benchmarkScore": round(benchmark_score, 2),
        "scoreDiff": round(strategy_score - benchmark_score, 2),
        "metrics": {
            "annualReturn": round(float(preview["annualReturn"]), 2),
            "totalReturn": round(float(preview["totalReturn"]), 2),
            "maxDrawdown": round(float(preview["maxDrawdown"]), 2),
            "sharpe": round(float(preview["sharpe"]), 2),
            "tradeCount": preview.get("tradeCount"),
        },
        "strategyDigest": {
            "entry": _describe_rule_list(strategy_config, "entry"),
            "exit": _describe_rule_list(strategy_config, "exit"),
        },
        "curveDiagnostics": curve_diagnostics,
        "timeRobustness": time_robustness,
        "reflection": {
            "analysis": analysis,
            "plan": action_plan,
        },
    }
    return json.dumps(memory_payload, ensure_ascii=False, separators=(",", ":"))


def _build_iteration_detail_analysis(task: AgentTask, iteration: AgentIteration) -> str:
    annual_return = float(iteration.annual_return) if iteration.annual_return is not None else None
    max_drawdown = float(iteration.max_drawdown) if iteration.max_drawdown is not None else None
    sharpe = float(iteration.sharpe) if iteration.sharpe is not None else None

    parts: list[str] = []
    if annual_return is not None or sharpe is not None or max_drawdown is not None:
        annual_text = f"{annual_return:.2f}%" if annual_return is not None else "-"
        sharpe_text = f"{sharpe:.2f}" if sharpe is not None else "-"
        drawdown_text = f"{max_drawdown:.2f}%" if max_drawdown is not None else "-"
        parts.append(f"本轮回测结果：年化收益 {annual_text}，Sharpe {sharpe_text}，最大回撤 {drawdown_text}。")

    if annual_return is not None and task.target_annual_return is not None:
        if annual_return >= float(task.target_annual_return):
            parts.append("收益已达到目标年化收益率。")
        else:
            parts.append("收益仍未达到目标年化收益率。")

    if max_drawdown is not None and task.max_drawdown_limit is not None:
        if max_drawdown <= float(task.max_drawdown_limit):
            parts.append("最大回撤仍在可接受范围内。")
        else:
            parts.append("最大回撤高于当前设定上限。")

    if sharpe is not None and task.min_sharpe is not None:
        if sharpe >= float(task.min_sharpe):
            parts.append("Sharpe 已达到当前目标。")
        else:
            parts.append("Sharpe 仍低于当前目标。")

    if iteration.summary:
        parts.append(f"本轮总结：{iteration.summary}")

    return "".join(parts) or "本轮已完成回测，但未生成单独分析，当前先依据结果摘要展示。"


def _build_iteration_detail_action_plan(task: AgentTask, iteration: AgentIteration) -> str:
    strategy_config = iteration.strategy_config or {}
    entry_desc = _describe_rule_list(strategy_config, "entry")
    exit_desc = _describe_rule_list(strategy_config, "exit")
    annual_return = float(iteration.annual_return) if iteration.annual_return is not None else None
    max_drawdown = float(iteration.max_drawdown) if iteration.max_drawdown is not None else None
    sharpe = float(iteration.sharpe) if iteration.sharpe is not None else None

    parts: list[str] = [f"当前策略的核心为买入“{entry_desc}”，卖出“{exit_desc}”。"]

    if annual_return is not None and task.target_annual_return is not None and annual_return < float(task.target_annual_return):
        parts.append("下一轮优先提升收益表现，可以尝试放宽有效买入条件或减少过早卖出。")
    if max_drawdown is not None and task.max_drawdown_limit is not None and max_drawdown > float(task.max_drawdown_limit):
        parts.append("需要进一步压低回撤，建议收紧退出条件或提高止损约束。")
    if sharpe is not None and task.min_sharpe is not None and sharpe < float(task.min_sharpe):
        parts.append("Sharpe 偏低，下一轮应减少噪声交易并提升信号质量。")

    if len(parts) == 1:
        parts.append("当前配置已经基本满足约束，下一轮可以围绕阈值微调或简化条件结构。")

    return "".join(parts)


def _build_iteration_detail_memory(
    task: AgentTask,
    iteration: AgentIteration,
    analysis: str,
    action_plan: str,
) -> str:
    annual_return = float(iteration.annual_return) if iteration.annual_return is not None else None
    max_drawdown = float(iteration.max_drawdown) if iteration.max_drawdown is not None else None
    sharpe = float(iteration.sharpe) if iteration.sharpe is not None else None
    annual_text = f"{annual_return:.2f}%" if annual_return is not None else "-"
    drawdown_text = f"{max_drawdown:.2f}%" if max_drawdown is not None else "-"
    sharpe_text = f"{sharpe:.2f}" if sharpe is not None else "-"
    return (
        f"第 {iteration.iteration_number} 轮："
        f"标的={task.asset_identifier}；"
        f"策略结果=年化 {annual_text} / 最大回撤 {drawdown_text} / Sharpe {sharpe_text}；"
        f"策略 DSL={json.dumps(iteration.strategy_config or {}, ensure_ascii=False)}；"
        f"分析={analysis}；"
        f"决策={action_plan}；"
        f"总结={iteration.summary}"
    )


