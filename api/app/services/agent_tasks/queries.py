from __future__ import annotations

from sqlalchemy import asc, desc, nullslast, or_

from app.extensions import db
from app.models.agent_iteration import AgentIteration
from app.models.agent_task import AgentTask
from app.models.user import User
from app.services.agent.memory import (
    _build_iteration_detail_action_plan,
    _build_iteration_detail_analysis,
    _build_iteration_detail_memory,
)
from app.services.agent.labels import _agent_intent_label
from app.services.agent_tasks.errors import AgentTaskError
from app.services.agent_tasks.helpers import _get_best_iteration, _score_iteration, _score_result
from app.services.performance_score import calculate_performance_score
from app.services.settings_service import get_performance_score_weights
from app.services.strategy_service import _load_asset_bars, _run_strategy_backtest
from app.services.agent.time_robustness import _resolve_preview_range


def list_agent_tasks(
    user: User,
    *,
    keyword: str = "",
    country_code: str = "",
    asset_type: str = "",
    status: str = "",
    sort_by: str = "",
    sort_order: str = "",
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

    if sort_by == "bestAnnualReturn":
        direction = asc if sort_order == "asc" else desc
        query = query.order_by(nullslast(direction(AgentTask.best_annual_return)), desc(AgentTask.updated_at), desc(AgentTask.id))
    else:
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
    task_payload["bestMaxDrawdown"] = (
        round(float(best_iteration.max_drawdown), 2)
        if best_iteration and best_iteration.max_drawdown is not None
        else None
    )
    task_payload["bestScore"] = _score_iteration(best_iteration, weights=score_weights)
    return {
        "task": task_payload,
        "iterations": [
            _serialize_agent_iteration_detail(task, item, score_weights=score_weights, bars=bars)
            for item in task.iterations
        ],
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
    score_weights = get_performance_score_weights(user)
    preview["score"] = round(_score_result(preview, weights=score_weights), 2)
    preview["benchmarkScore"] = round(
        calculate_performance_score(
            preview.get("benchmarkAnnualReturn"),
            preview.get("benchmarkSharpe"),
            preview.get("benchmarkMaxDrawdown"),
            weights=score_weights,
        ),
        2,
    )
    return preview


def _serialize_agent_iteration_detail(
    task: AgentTask,
    iteration: AgentIteration,
    *,
    score_weights: dict[str, float] | None = None,
    bars: list[dict] | None = None,
) -> dict:
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
    preview_summary = _build_iteration_equity_preview(iteration, bars or [], score_weights=score_weights)
    payload["equityPreview"] = preview_summary.get("equityPreview") if preview_summary else None
    payload["benchmarkScore"] = preview_summary.get("benchmarkScore") if preview_summary else None
    return payload


def _build_iteration_equity_preview(
    iteration: AgentIteration,
    bars: list[dict],
    *,
    score_weights: dict[str, float] | None = None,
) -> dict | None:
    if not bars or not iteration.strategy_config:
        return None
    try:
        preview = _run_strategy_backtest(bars, iteration.strategy_config or {})
    except Exception:  # noqa: BLE001
        return None
    return {
        "equityPreview": {
            "equityCurve": _downsample_curve(preview.get("equityCurve") or []),
            "benchmarkCurve": _downsample_curve(preview.get("benchmarkCurve") or []),
        },
        "benchmarkScore": round(
            calculate_performance_score(
                preview.get("benchmarkAnnualReturn"),
                preview.get("benchmarkSharpe"),
                preview.get("benchmarkMaxDrawdown"),
                weights=score_weights,
            ),
            2,
        ),
    }


def _downsample_curve(curve: list[dict], max_points: int = 80) -> list[dict]:
    if len(curve) <= max_points:
        return curve
    step = (len(curve) - 1) / (max_points - 1)
    sampled: list[dict] = []
    seen: set[int] = set()
    for index in range(max_points):
        source_index = round(index * step)
        if source_index in seen:
            continue
        seen.add(source_index)
        sampled.append(curve[source_index])
    return sampled
