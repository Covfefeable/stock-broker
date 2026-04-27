from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.models.agent_iteration import AgentIteration
from app.models.agent_task import AgentTask
from app.services.agent.curve_diagnostics import _build_equity_curve_diagnostics
from app.services.agent.generation import _generate_strategy_with_ai
from app.services.agent.memory import _build_iteration_memory, _select_agent_prompt_memories
from app.services.agent.strategy_description import _describe_rule_list
from app.services.agent.time_robustness import _build_time_robustness_summary
from app.services.agent_tasks.errors import AgentTaskError
from app.services.agent_tasks.helpers import (
    _build_action_plan_fallback,
    _build_agent_research_state,
    _build_analysis_fallback,
    _build_iteration_summary,
    _build_noop_strategy_config,
    _enrich_agent_thoughts,
    _is_better_result,
    _score_result,
)
from app.services.data_center_service import log_event
from app.services.settings_service import get_performance_score_weights
from app.services.strategy_service import _load_asset_bars, _run_strategy_backtest


def run_agent_iterations(task: AgentTask, *, task_id: str | None = None) -> dict:
    db.session.refresh(task)
    if task.stop_requested:
        return mark_agent_task_stopped(task, task_id=task_id)

    task.status = "running"
    task.celery_task_id = task_id
    task.started_at = datetime.now(timezone.utc)
    task.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    log_event(
        user=task.user,
        task_id=task_id,
        event_type="agent",
        event_name="agent_task_running",
        source=task.name,
        target=task.asset_name,
        status="running",
        level="info",
        message=f"{task.name} 开始执行，共计划 {task.max_iterations} 轮迭代。",
    )

    bars = _load_asset_bars(
        task.asset_type,
        task.asset_identifier,
        task.country_code,
        {
            "risk": {
                "backtestStartDate": task.backtest_start_date.isoformat(),
                "backtestEndDate": task.backtest_end_date.isoformat(),
            }
        },
    )
    if not bars:
        raise AgentTaskError("当前标的没有可用于 Agent 任务的历史日线数据。")

    score_weights = get_performance_score_weights(task.user)
    benchmark_preview = _run_strategy_backtest(bars, _build_noop_strategy_config(task))
    benchmark_metrics = {
        "benchmarkReturn": benchmark_preview["benchmarkReturn"],
        "benchmarkAnnualReturn": benchmark_preview["benchmarkAnnualReturn"],
        "benchmarkMaxDrawdown": benchmark_preview["benchmarkMaxDrawdown"],
        "benchmarkSharpe": benchmark_preview["benchmarkSharpe"],
        "benchmarkVolatility": benchmark_preview["benchmarkVolatility"],
    }

    best_result: dict | None = None
    iteration_results: list[dict] = []
    iteration_memory_rows: list[dict] = []

    for iteration in range(1, task.max_iterations + 1):
        sampled_memories = _select_agent_prompt_memories(iteration_memory_rows)
        research_state = _build_agent_research_state(
            task,
            iteration,
            iteration_results,
            best_result,
            benchmark_metrics,
        )
        generation_result = _generate_strategy_with_ai(
            task,
            sampled_memories,
            benchmark_metrics,
            research_state,
        )
        strategy_config = generation_result["strategyConfig"]
        preview = _run_strategy_backtest(bars, strategy_config)
        curve_diagnostics = _build_equity_curve_diagnostics(preview)
        time_robustness = _build_time_robustness_summary(
            task,
            strategy_config,
            score_weights=score_weights,
        )
        analysis_text = generation_result.get("analysis") or _build_analysis_fallback(
            task,
            preview,
            benchmark_metrics,
        )
        action_plan_text = generation_result.get("actionPlan") or _build_action_plan_fallback(
            strategy_config,
            preview,
            benchmark_metrics,
        )
        analysis_text, action_plan_text = _enrich_agent_thoughts(
            analysis_text,
            action_plan_text,
            generation_result,
            research_state,
        )
        summary = _build_iteration_summary(
            task,
            iteration,
            strategy_config,
            preview,
            best_result,
            benchmark_metrics,
            analysis_text,
            action_plan_text,
            generation_result.get("mode"),
            generation_result.get("intent"),
            score_weights=score_weights,
        )
        memory_text = _build_iteration_memory(
            iteration,
            strategy_config,
            preview,
            benchmark_metrics,
            analysis_text,
            action_plan_text,
            summary,
            generation_result,
            research_state,
            curve_diagnostics,
            time_robustness,
            score_weights=score_weights,
        )

        iteration_row = AgentIteration(
            task_id=task.id,
            iteration_number=iteration,
            status="success",
            annual_return=Decimal(str(preview["annualReturn"])),
            max_drawdown=Decimal(str(preview["maxDrawdown"])),
            sharpe=Decimal(str(preview["sharpe"])),
            strategy_config=strategy_config,
            intent=generation_result.get("intent"),
            memory=memory_text,
            time_robustness=time_robustness,
            analysis=analysis_text,
            action_plan=action_plan_text,
            summary=summary,
        )
        db.session.add(iteration_row)

        is_best_result = _is_better_result(preview, best_result, weights=score_weights)
        if is_best_result:
            best_result = preview
            task.best_annual_return = Decimal(str(preview["annualReturn"]))
            task.best_sharpe = Decimal(str(preview["sharpe"]))
            task.best_strategy_config = strategy_config
            task.best_summary = summary

        iteration_results.append(
            {
                "iteration": iteration,
                "mode": generation_result.get("mode") or "explore_new",
                "intent": generation_result.get("intent") or "trend_following",
                "score": _score_result(preview, weights=score_weights),
                "isBest": is_best_result,
                "annualReturn": preview["annualReturn"],
                "totalReturn": preview["totalReturn"],
                "maxDrawdown": preview["maxDrawdown"],
                "sharpe": preview["sharpe"],
                "tradeCount": preview.get("tradeCount"),
                "timeRobustness": time_robustness.get("summary") or {},
                "entry": _describe_rule_list(strategy_config, "entry"),
                "exit": _describe_rule_list(strategy_config, "exit"),
            }
        )

        iteration_memory_rows.append(
            {
                "iteration": iteration,
                "score": iteration_results[-1]["score"],
                "memory": memory_text,
            }
        )

        task.current_iteration = iteration
        task.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        log_event(
            user=task.user,
            task_id=task_id,
            event_type="agent",
            event_name="agent_iteration",
            source=task.name,
            target=task.asset_name,
            status="running",
            level="info",
            message=(
                f"第 {iteration}/{task.max_iterations} 轮完成："
                f"综合分 {_score_result(preview, weights=score_weights):.2f}，"
                f"年化 {preview['annualReturn']:.2f}%，"
                f"回撤 {preview['maxDrawdown']:.2f}%，"
                f"Sharpe {preview['sharpe']:.2f}。"
            ),
            records_affected=iteration,
        )

        db.session.refresh(task)
        if task.stop_requested:
            return mark_agent_task_stopped(task, task_id=task_id)

    task.status = "success"
    task.finished_at = datetime.now(timezone.utc)
    task.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    log_event(
        user=task.user,
        task_id=task_id,
        event_type="agent",
        event_name="agent_task_finished",
        source=task.name,
        target=task.asset_name,
        status="success",
        level="info",
        message=f"{task.name} 已完成，共执行 {task.current_iteration} 轮迭代。",
    )

    return {
        "taskId": task.id,
        "iterations": task.current_iteration,
        "bestAnnualReturn": float(task.best_annual_return) if task.best_annual_return is not None else None,
        "bestSharpe": float(task.best_sharpe) if task.best_sharpe is not None else None,
    }


def mark_agent_task_stopped(task: AgentTask, *, task_id: str | None = None) -> dict:
    task.status = "stopped"
    task.finished_at = datetime.now(timezone.utc)
    task.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    log_event(
        user=task.user,
        task_id=task_id or task.celery_task_id,
        event_type="agent",
        event_name="agent_task_stopped",
        source=task.name,
        target=task.asset_name,
        status="stopped",
        level="warning",
        message=f"{task.name} 已停止，共执行 {task.current_iteration} 轮迭代。",
    )

    return {
        "taskId": task.id,
        "status": task.status,
        "iterations": task.current_iteration,
        "bestAnnualReturn": float(task.best_annual_return) if task.best_annual_return is not None else None,
        "bestSharpe": float(task.best_sharpe) if task.best_sharpe is not None else None,
    }


def mark_agent_task_failed(task: AgentTask, message: str, *, celery_task_id: str | None = None) -> None:
    task.status = "failure"
    task.finished_at = datetime.now(timezone.utc)
    task.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    log_event(
        user=task.user,
        task_id=celery_task_id,
        event_type="agent",
        event_name="agent_task_failed",
        source=task.name,
        target=task.asset_name,
        status="failed",
        level="error",
        message=message,
    )
