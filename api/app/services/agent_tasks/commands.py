from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.models.agent_task import AgentTask
from app.models.scheduled_plan_run import ScheduledPlanRun
from app.models.user import User
from app.services.agent_tasks.errors import AgentTaskError
from app.services.agent_tasks.helpers import (
    _parse_date,
    _parse_decimal,
    _parse_int,
    _resolve_ai_model,
    _resolve_asset_name,
)
from app.services.agent_tasks.queries import get_agent_task
from app.services.data_center import log_event
from app.services.scheduled_plans import ScheduledPlanError, ensure_agent_task_not_referenced
from app.services.strategies import list_strategy_asset_options


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
        initial_capital=Decimal("100000"),
        position_size=Decimal("1"),
        stop_loss=Decimal("0"),
        take_profit=Decimal("0"),
        min_add_position_interval=0,
        max_holding_days=0,
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
    try:
        ensure_agent_task_not_referenced(user, task.id)
    except ScheduledPlanError as exc:
        raise AgentTaskError(str(exc)) from exc
    ScheduledPlanRun.query.filter(
        ScheduledPlanRun.user_id == user.id,
        ScheduledPlanRun.generated_agent_task_id == task.id,
    ).update({"generated_agent_task_id": None}, synchronize_session=False)
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
