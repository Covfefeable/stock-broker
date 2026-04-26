from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, or_

from app.extensions import db
from app.models.agent_iteration import AgentIteration
from app.models.agent_task import AgentTask
from app.models.index_asset import IndexAsset
from app.models.stock import Stock
from app.models.user import User
from app.services.agent.curve_diagnostics import _build_equity_curve_diagnostics
from app.services.agent.generation import _generate_strategy_with_ai
from app.services.agent.labels import _agent_intent_label, _agent_mode_label
from app.services.agent.memory import (
    _build_iteration_detail_action_plan,
    _build_iteration_detail_analysis,
    _build_iteration_detail_memory,
    _build_iteration_memory,
    _select_agent_prompt_memories,
)
from app.services.agent.strategy_description import _describe_group
from app.services.agent.time_robustness import (
    _build_time_robustness_summary,
    _resolve_preview_range,
)
from app.services.data_center_service import log_event
from app.services.performance_score import calculate_performance_score
from app.services.settings_service import get_performance_score_weights
from app.services.settings_service import get_or_create_settings
from app.services.strategy_service import (
    _load_asset_bars,
    _run_strategy_backtest,
    list_strategy_asset_options,
)


class AgentTaskError(ValueError):
    pass


AGENT_RECENT_MEMORY_LIMIT = 5


def list_agent_tasks(
    user: User,
    *,
    keyword: str = "",
    country_code: str = "",
    asset_type: str = "",
    status: str = "",
    page: int = 1,
    page_size: int = 10,
) -> dict:
    query = AgentTask.query.filter(AgentTask.user_id == user.id)

    normalized_keyword = keyword.strip()
    if normalized_keyword:
        pattern = f"%{normalized_keyword}%"
        query = query.filter(
            or_(
                AgentTask.name.ilike(pattern),
                AgentTask.asset_name.ilike(pattern),
                AgentTask.asset_identifier.ilike(pattern),
            )
        )

    if country_code:
        query = query.filter(AgentTask.country_code == country_code)
    if asset_type:
        query = query.filter(AgentTask.asset_type == asset_type)
    if status:
        query = query.filter(AgentTask.status == status)

    query = query.order_by(desc(AgentTask.updated_at), desc(AgentTask.id))
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    country_options = [
        value
        for value in db.session.query(AgentTask.country_code)
        .filter(AgentTask.user_id == user.id)
        .distinct()
        .order_by(AgentTask.country_code.asc())
        .all()
    ]
    status_options = [
        value
        for value in db.session.query(AgentTask.status)
        .filter(AgentTask.user_id == user.id)
        .distinct()
        .order_by(AgentTask.status.asc())
        .all()
    ]

    return {
        "items": [item.to_dict() for item in items],
        "pagination": {"page": page, "pageSize": page_size, "total": total},
        "filters": {
            "countryCodes": [value for (value,) in country_options if value],
            "statuses": [value for (value,) in status_options if value],
        },
    }


def get_agent_task(user: User, task_id: int) -> AgentTask:
    task = AgentTask.query.filter(AgentTask.id == task_id, AgentTask.user_id == user.id).first()
    if not task:
        raise AgentTaskError("未找到对应的 Agent 任务。")
    return task


def get_agent_task_detail(user: User, task_id: int) -> dict:
    task = get_agent_task(user, task_id)
    task_payload = task.to_dict()
    score_weights = get_performance_score_weights(user)
    best_iteration = _get_best_iteration(task, score_weights=score_weights)
    task_payload["bestMaxDrawdown"] = (
        round(float(best_iteration.max_drawdown), 2)
        if best_iteration and best_iteration.max_drawdown is not None
        else None
    )
    task_payload["bestScore"] = _score_iteration(best_iteration, weights=score_weights)
    return {
        "task": task_payload,
        "iterations": [_serialize_agent_iteration_detail(task, item, score_weights=score_weights) for item in task.iterations],
    }


def preview_agent_iteration(
    user: User,
    task_id: int,
    iteration_id: int,
    *,
    range_key: str | None = None,
) -> dict:
    task = get_agent_task(user, task_id)
    iteration = AgentIteration.query.filter(
        AgentIteration.id == iteration_id,
        AgentIteration.task_id == task.id,
    ).first()
    if not iteration:
        raise AgentTaskError("未找到对应的迭代记录。")

    range_config = _resolve_preview_range(task, range_key)
    bars = _load_asset_bars(
        task.asset_type,
        task.asset_identifier,
        task.country_code,
        {
            "risk": {
                "backtestStartDate": range_config["startDate"].isoformat(),
                "backtestEndDate": range_config["endDate"].isoformat(),
            }
        },
    )
    if not bars:
        raise AgentTaskError("当前标的没有可用于预览收益的历史日线数据。")

    preview = _run_strategy_backtest(bars, iteration.strategy_config or {})
    preview["rangeKey"] = range_config["key"]
    preview["rangeLabel"] = range_config["label"]
    return preview


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


def _serialize_agent_iteration_detail(task: AgentTask, iteration: AgentIteration, *, score_weights: dict[str, float] | None = None) -> dict:
    payload = iteration.to_dict()
    payload["score"] = _score_iteration(iteration, weights=score_weights)
    payload["intentLabel"] = _agent_intent_label(payload.get("intent")) if payload.get("intent") else None
    analysis = (payload.get("analysis") or "").strip()
    action_plan = (payload.get("actionPlan") or "").strip()
    memory = (payload.get("memory") or "").strip()

    if not analysis:
        analysis = _build_iteration_detail_analysis(task, iteration)
    if not action_plan:
        action_plan = _build_iteration_detail_action_plan(task, iteration)
    if not memory:
        memory = _build_iteration_detail_memory(task, iteration, analysis, action_plan)

    payload["analysis"] = analysis
    payload["actionPlan"] = action_plan
    payload["memory"] = memory
    return payload


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


def create_agent_task(user: User, payload: dict) -> AgentTask:
    name = str(payload.get("name", "")).strip()
    country_code = str(payload.get("countryCode", "")).strip().upper()
    asset_type = str(payload.get("assetType", "")).strip()
    asset_identifier = str(payload.get("assetIdentifier", "")).strip()
    note = str(payload.get("note", "")).strip() or None

    if not name:
        raise AgentTaskError("请输入任务名称。")
    if not country_code:
        raise AgentTaskError("请选择国家/地区。")
    if asset_type not in {"stock", "index"}:
        raise AgentTaskError("请选择股票或指数。")
    if not asset_identifier:
        raise AgentTaskError("请选择具体标的。")

    ai_model_payload = _resolve_ai_model(user, payload.get("aiModel"))
    asset_name = _resolve_asset_name(country_code, asset_type, asset_identifier)

    task = AgentTask(
        user_id=user.id,
        name=name,
        country_code=country_code,
        asset_type=asset_type,
        asset_identifier=asset_identifier,
        asset_name=asset_name,
        ai_model_name=ai_model_payload["name"] or ai_model_payload["model"],
        ai_model_config=ai_model_payload,
        note=note,
        status="queued",
        max_iterations=_parse_int(payload.get("maxIterations"), "最大迭代次数"),
        target_annual_return=_parse_decimal(payload.get("targetAnnualReturn"), "目标年化收益率"),
        max_drawdown_limit=_parse_decimal(payload.get("maxDrawdownLimit"), "最大可接受回撤"),
        min_sharpe=_parse_decimal(payload.get("minSharpe"), "最低 Sharpe"),
        initial_capital=_parse_decimal(payload.get("initialCapital"), "初始资金"),
        position_size=_parse_decimal(payload.get("positionSize"), "每次买入仓位"),
        stop_loss=_parse_decimal(payload.get("stopLoss"), "止损比例"),
        take_profit=_parse_decimal(payload.get("takeProfit"), "止盈比例"),
        min_add_position_interval=_parse_int(payload.get("minAddPositionInterval", 3), "最小加仓间隔"),
        max_holding_days=_parse_int(payload.get("maxHoldingDays"), "最大持仓天数"),
        backtest_start_date=_parse_date(payload.get("backtestStartDate"), "回测开始日期"),
        backtest_end_date=_parse_date(payload.get("backtestEndDate"), "回测结束日期"),
    )
    db.session.add(task)
    db.session.commit()

    from app.tasks.agent import run_agent_task  # local import to avoid circulars

    async_result = run_agent_task.delay(task_id=task.id, user_id=user.id)
    task.celery_task_id = async_result.id
    task.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    log_event(
        user=user,
        task_id=async_result.id,
        event_type="agent",
        event_name="agent_task_enqueued",
        source=task.name,
        target=task.asset_name,
        status="queued",
        level="info",
        message=f"{task.name} 已加入队列，等待开始迭代。",
    )

    return task


def delete_agent_task(user: User, task_id: int) -> None:
    task = get_agent_task(user, task_id)
    db.session.delete(task)
    db.session.commit()


def update_agent_task_name(user: User, task_id: int, name: str) -> AgentTask:
    task = get_agent_task(user, task_id)
    normalized_name = str(name or "").strip()
    if not normalized_name:
        raise AgentTaskError("请输入任务名称。")
    task.name = normalized_name
    task.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return task


def rerun_agent_task(user: User, task_id: int) -> AgentTask:
    task = get_agent_task(user, task_id)
    return create_agent_task(
        user,
        {
            "name": f"{task.name}（重新运行）",
            "countryCode": task.country_code,
            "assetType": task.asset_type,
            "assetIdentifier": task.asset_identifier,
            "aiModel": task.ai_model_config,
            "note": task.note,
            "maxIterations": task.max_iterations,
            "targetAnnualReturn": task.target_annual_return,
            "maxDrawdownLimit": task.max_drawdown_limit,
            "minSharpe": task.min_sharpe,
            "initialCapital": task.initial_capital,
            "positionSize": task.position_size,
            "stopLoss": task.stop_loss,
            "takeProfit": task.take_profit,
            "minAddPositionInterval": task.min_add_position_interval,
            "maxHoldingDays": task.max_holding_days,
            "backtestStartDate": task.backtest_start_date.isoformat(),
            "backtestEndDate": task.backtest_end_date.isoformat(),
        },
    )


def request_stop_agent_task(user: User, task_id: int) -> AgentTask:
    task = get_agent_task(user, task_id)
    if task.status in {"success", "failure", "stopped"}:
        raise AgentTaskError("当前 Agent 任务已结束，无法停止。")

    now = datetime.now(timezone.utc)
    task.stop_requested = True
    task.stop_requested_at = now
    task.updated_at = now

    if task.status == "queued":
        task.status = "stopped"
        task.finished_at = now
        db.session.commit()
        log_event(
            user=task.user,
            task_id=task.celery_task_id,
            event_type="agent",
            event_name="agent_task_stopped",
            source=task.name,
            target=task.asset_name,
            status="stopped",
            level="warning",
            message=f"{task.name} 已在开始前停止。",
        )
        return task

    db.session.commit()
    log_event(
        user=task.user,
        task_id=task.celery_task_id,
        event_type="agent",
        event_name="agent_task_stop_requested",
        source=task.name,
        target=task.asset_name,
        status="running",
        level="warning",
        message=f"{task.name} 已收到停止信号，将在当前轮结束后停止。",
    )
    return task


def get_agent_task_asset_options(country_code: str, asset_type: str) -> dict:
    try:
        return list_strategy_asset_options(country_code, asset_type)
    except Exception as exc:  # noqa: BLE001
        raise AgentTaskError(str(exc)) from exc


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
                "entry": _describe_group(strategy_config.get("entry") or {}),
                "exit": _describe_group(strategy_config.get("exit") or {}),
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
    entry_desc = _describe_group(strategy_config.get("entry") or {})
    exit_desc = _describe_group(strategy_config.get("exit") or {})

    summary_parts = [
        f"本轮模式：{_agent_mode_label(mode)}。",
        f"交易风格：{_agent_intent_label(intent)}。",
        f"本轮买入规则为“{entry_desc}”，卖出规则为“{exit_desc}”。",
        f"回测结果：年化收益 {preview['annualReturn']:.2f}% ，最大回撤 {preview['maxDrawdown']:.2f}% ，Sharpe {preview['sharpe']:.2f}。",
        f"持续持有对照：年化收益 {benchmark_metrics['benchmarkAnnualReturn']:.2f}% ，总收益 {benchmark_metrics['benchmarkReturn']:.2f}% 。",
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
        f"持续持有年化收益 {benchmark_metrics['benchmarkAnnualReturn']:.2f}% ，最大回撤 {benchmark_metrics['benchmarkMaxDrawdown']:.2f}%。",
    ]
    if preview["annualReturn"] >= benchmark_metrics["benchmarkAnnualReturn"]:
        parts.append("当前策略在收益层面已达到或超过持续持有。")
    else:
        parts.append("当前策略在收益层面仍弱于持续持有。")
    if preview["maxDrawdown"] <= benchmark_metrics["benchmarkMaxDrawdown"]:
        parts.append("但它在回撤控制上更占优。")
    return "".join(parts)


def _build_action_plan_fallback(strategy_config: dict, preview: dict, benchmark_metrics: dict[str, float]) -> str:
    entry_desc = _describe_group(strategy_config.get("entry") or {})
    exit_desc = _describe_group(strategy_config.get("exit") or {})
    if preview["annualReturn"] < benchmark_metrics["benchmarkAnnualReturn"]:
        return f"继续调整当前策略，重点优化买入“{entry_desc}”和卖出“{exit_desc}”的阈值，争取先超过持续持有。"
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
            "initialCapital": float(task.initial_capital),
            "positionSize": float(task.position_size),
            "stopLoss": float(task.stop_loss),
            "takeProfit": float(task.take_profit),
            "minAddPositionInterval": task.min_add_position_interval,
            "maxHoldingDays": task.max_holding_days,
            "backtestStartDate": task.backtest_start_date.isoformat(),
            "backtestEndDate": task.backtest_end_date.isoformat(),
        },
    }


