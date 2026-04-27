from __future__ import annotations

from datetime import datetime, time, timezone
from decimal import Decimal

from sqlalchemy import desc, or_

from app.extensions import db, redis_client
from app.models.agent_iteration import AgentIteration
from app.models.agent_task import AgentTask
from app.models.scheduled_plan import ScheduledPlan
from app.models.scheduled_plan_run import ScheduledPlanRun
from app.models.user import User
from app.services.agent_tasks.helpers import _score_iteration
from app.services.backtest_lab import evaluate_strategy
from app.services.data_center import log_event
from app.services.scheduled_plans.errors import ScheduledPlanError
from app.services.scheduled_plans.schedule import calculate_next_run_at
from app.services.settings import get_performance_score_weights
from app.services.strategies import create_strategy

PLAN_STATUSES = {"enabled", "disabled", "paused_failed"}
FREQUENCY_TYPES = {"monthly", "weekly", "daily", "hourly"}
RUNNING_RUN_STATUSES = {"pending", "running"}
INTERNAL_MAX_FAILURES = 3


def list_scheduled_plans(
    user: User,
    *,
    keyword: str = "",
    status: str = "",
    frequency_type: str = "",
    page: int = 1,
    page_size: int = 10,
) -> dict:
    query = ScheduledPlan.query.filter(ScheduledPlan.user_id == user.id)
    normalized_keyword = keyword.strip()
    if normalized_keyword:
        pattern = f"%{normalized_keyword}%"
        query = query.join(AgentTask).filter(or_(ScheduledPlan.name.ilike(pattern), AgentTask.name.ilike(pattern)))
    if status:
        query = query.filter(ScheduledPlan.status == status)
    if frequency_type:
        query = query.filter(ScheduledPlan.frequency_type == frequency_type)
    query = query.order_by(desc(ScheduledPlan.updated_at), desc(ScheduledPlan.id))
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [item.to_dict() for item in items],
        "pagination": {"page": page, "pageSize": page_size, "total": total},
    }


def get_scheduled_plan(user: User, plan_id: int) -> ScheduledPlan:
    plan = ScheduledPlan.query.filter(ScheduledPlan.id == plan_id, ScheduledPlan.user_id == user.id).first()
    if not plan:
        raise ScheduledPlanError("未找到对应的计划任务。")
    return plan


def get_scheduled_plan_detail(user: User, plan_id: int) -> dict:
    plan = get_scheduled_plan(user, plan_id)
    runs = (
        ScheduledPlanRun.query.filter(ScheduledPlanRun.plan_id == plan.id, ScheduledPlanRun.user_id == user.id)
        .order_by(desc(ScheduledPlanRun.created_at), desc(ScheduledPlanRun.id))
        .limit(30)
        .all()
    )
    return {"plan": plan.to_dict(), "runs": [run.to_dict() for run in runs]}


def list_agent_task_options(user: User) -> dict:
    tasks = AgentTask.query.filter(AgentTask.user_id == user.id).order_by(desc(AgentTask.updated_at), desc(AgentTask.id)).all()
    return {"items": [task.to_dict() for task in tasks]}


def create_scheduled_plan(user: User, payload: dict) -> ScheduledPlan:
    plan = ScheduledPlan(user_id=user.id)
    _apply_plan_payload(plan, user, payload)
    now = datetime.now(timezone.utc)
    plan.created_at = now
    plan.updated_at = now
    plan.next_run_at = calculate_next_run_at(plan, after=now) if plan.status == "enabled" else None
    db.session.add(plan)
    db.session.commit()
    return plan


def update_scheduled_plan(user: User, plan_id: int, payload: dict) -> ScheduledPlan:
    plan = get_scheduled_plan(user, plan_id)
    _apply_plan_payload(plan, user, payload)
    now = datetime.now(timezone.utc)
    plan.updated_at = now
    plan.next_run_at = calculate_next_run_at(plan, after=now) if plan.status == "enabled" else None
    db.session.commit()
    return plan


def delete_scheduled_plan(user: User, plan_id: int) -> None:
    plan = get_scheduled_plan(user, plan_id)
    db.session.delete(plan)
    db.session.commit()


def set_scheduled_plan_status(user: User, plan_id: int, status: str) -> ScheduledPlan:
    if status not in {"enabled", "disabled"}:
        raise ScheduledPlanError("计划状态无效。")
    plan = get_scheduled_plan(user, plan_id)
    plan.status = status
    plan.updated_at = datetime.now(timezone.utc)
    plan.next_run_at = calculate_next_run_at(plan, after=plan.updated_at) if status == "enabled" else None
    db.session.commit()
    return plan


def run_scheduled_plan_now(user: User, plan_id: int) -> dict:
    plan = get_scheduled_plan(user, plan_id)
    return trigger_scheduled_plan(plan, trigger_type="manual")


def scan_due_scheduled_plans(*, task_id: str | None = None) -> dict:
    now = datetime.now(timezone.utc)
    plans = (
        ScheduledPlan.query.filter(
            ScheduledPlan.status == "enabled",
            ScheduledPlan.next_run_at.isnot(None),
            ScheduledPlan.next_run_at <= now,
        )
        .order_by(ScheduledPlan.next_run_at.asc(), ScheduledPlan.id.asc())
        .limit(50)
        .all()
    )
    triggered = 0
    skipped = 0
    failed = 0
    for plan in plans:
        try:
            result = trigger_scheduled_plan(plan, trigger_type="schedule", scheduler_task_id=task_id)
            if result.get("status") == "skipped":
                skipped += 1
            else:
                triggered += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            _record_plan_failure(plan, str(exc))
    return {"scanned": len(plans), "triggered": triggered, "skipped": skipped, "failed": failed}


def trigger_scheduled_plan(
    plan: ScheduledPlan,
    *,
    trigger_type: str,
    scheduler_task_id: str | None = None,
) -> dict:
    lock_key = f"scheduled-plan:trigger:{plan.id}"
    lock_acquired = _acquire_lock(lock_key, 600)
    if not lock_acquired:
        return {"planId": plan.id, "status": "skipped", "reason": "locked"}
    try:
        now = datetime.now(timezone.utc)
        active_run = ScheduledPlanRun.query.filter(
            ScheduledPlanRun.plan_id == plan.id,
            ScheduledPlanRun.status.in_(RUNNING_RUN_STATUSES),
        ).first()
        if active_run:
            plan.next_run_at = calculate_next_run_at(plan, after=now)
            plan.updated_at = now
            db.session.commit()
            return {"planId": plan.id, "status": "skipped", "reason": "active_run"}

        source_task = plan.agent_task
        if not source_task:
            raise ScheduledPlanError("计划关联的 Agent 任务不存在。")

        generated_task = _clone_agent_task_for_plan(plan, source_task)
        run = ScheduledPlanRun(
            plan_id=plan.id,
            user_id=plan.user_id,
            agent_task_id=source_task.id,
            generated_agent_task_id=generated_task.id,
            status="pending",
            trigger_type=trigger_type,
            saved_strategy_ids=[],
            started_at=now,
        )
        db.session.add(run)
        db.session.flush()

        from app.tasks.agent import run_agent_task

        async_result = run_agent_task.delay(task_id=generated_task.id, user_id=plan.user_id)
        generated_task.celery_task_id = async_result.id
        run.status = "running"
        plan.last_run_at = now
        plan.next_run_at = calculate_next_run_at(plan, after=now) if plan.status == "enabled" else None
        plan.updated_at = now
        db.session.commit()

        log_event(
            user=plan.user,
            task_id=async_result.id,
            event_type="agent",
            event_name="scheduled_plan_triggered",
            source=plan.name,
            target=source_task.name,
            status="queued",
            level="info",
            message=f"{plan.name} 已触发 Agent 任务：{generated_task.name}。",
        )
        return {"planId": plan.id, "runId": run.id, "taskId": generated_task.id, "status": "running"}
    finally:
        _release_lock(lock_key)


def complete_scheduled_plan_run_for_agent(
    task: AgentTask,
    *,
    success: bool,
    error_message: str | None = None,
) -> None:
    run = (
        ScheduledPlanRun.query.filter(ScheduledPlanRun.generated_agent_task_id == task.id)
        .order_by(desc(ScheduledPlanRun.created_at), desc(ScheduledPlanRun.id))
        .first()
    )
    if not run or run.status not in RUNNING_RUN_STATUSES:
        return

    plan = run.plan
    now = datetime.now(timezone.utc)
    if not success:
        run.status = "failed"
        run.error_message = error_message or "Agent 任务执行失败。"
        run.finished_at = now
        run.updated_at = now
        _record_plan_failure(plan, run.error_message, commit=False)
        db.session.commit()
        return

    try:
        saved_strategy_ids = _save_top_strategies_for_run(run)
        run.status = "success"
        run.saved_strategy_ids = saved_strategy_ids
        run.error_message = None
        run.finished_at = now
        run.updated_at = now
        plan.failure_count = 0
        plan.last_success_at = now
        plan.last_error_message = None
        plan.updated_at = now
        db.session.commit()
    except Exception as exc:  # noqa: BLE001
        run.status = "failed"
        run.error_message = f"保存计划策略失败：{exc}"
        run.finished_at = now
        run.updated_at = now
        _record_plan_failure(plan, run.error_message, commit=False)
        db.session.commit()


def ensure_agent_task_not_referenced(user: User, task_id: int) -> None:
    plans = (
        ScheduledPlan.query.filter(ScheduledPlan.user_id == user.id, ScheduledPlan.agent_task_id == task_id)
        .order_by(ScheduledPlan.updated_at.desc())
        .limit(3)
        .all()
    )
    if not plans:
        return
    names = "、".join(plan.name for plan in plans)
    suffix = "等计划" if len(plans) >= 3 else "计划"
    raise ScheduledPlanError(f"「{names}」{suffix}正在使用该 Agent 任务，请先删除计划。")


def _apply_plan_payload(plan: ScheduledPlan, user: User, payload: dict) -> None:
    name = str(payload.get("name", "")).strip()
    agent_task_id = _parse_int(payload.get("agentTaskId"), "Agent 任务")
    frequency_type = str(payload.get("frequencyType", "")).strip()
    status = str(payload.get("status", "enabled")).strip() or "enabled"

    if not name:
        raise ScheduledPlanError("请输入计划名称。")
    if frequency_type not in FREQUENCY_TYPES:
        raise ScheduledPlanError("请选择有效的执行频率。")
    if status not in PLAN_STATUSES:
        raise ScheduledPlanError("计划状态无效。")

    agent_task = AgentTask.query.filter(AgentTask.id == agent_task_id, AgentTask.user_id == user.id).first()
    if not agent_task:
        raise ScheduledPlanError("请选择有效的 Agent 任务。")

    plan.name = name
    plan.agent_task_id = agent_task.id
    plan.frequency_type = frequency_type
    plan.timezone = "Asia/Shanghai"
    plan.status = status
    plan.save_top_n = max(1, min(_parse_int(payload.get("saveTopN", 1), "保存最佳策略数量"), 10))
    plan.score_threshold_enabled = bool(payload.get("scoreThresholdEnabled"))
    plan.score_threshold = (
        _parse_decimal(payload.get("scoreThreshold"), "保存阈值")
        if plan.score_threshold_enabled
        else None
    )

    plan.time_of_day = None
    plan.minute_of_hour = None
    plan.month_days = []
    plan.use_last_day = False
    plan.weekdays = []

    if frequency_type in {"monthly", "weekly", "daily"}:
        plan.time_of_day = _parse_time(payload.get("timeOfDay"))
    if frequency_type == "monthly":
        plan.month_days = _parse_int_list(payload.get("monthDays"), 1, 31, "每月执行日期")
        plan.use_last_day = bool(payload.get("useLastDay"))
        if not plan.month_days and not plan.use_last_day:
            raise ScheduledPlanError("请选择每月执行日期。")
    elif frequency_type == "weekly":
        plan.weekdays = _parse_int_list(payload.get("weekdays"), 1, 7, "每周执行星期")
        if not plan.weekdays:
            raise ScheduledPlanError("请选择每周执行星期。")
    elif frequency_type == "hourly":
        plan.minute_of_hour = _parse_int(payload.get("minuteOfHour"), "每小时执行分钟")
        if not 0 <= plan.minute_of_hour <= 59:
            raise ScheduledPlanError("每小时执行分钟必须在 0 到 59 之间。")


def _clone_agent_task_for_plan(plan: ScheduledPlan, source_task: AgentTask) -> AgentTask:
    now = datetime.now(timezone.utc)
    task = AgentTask(
        user_id=source_task.user_id,
        name=f"{plan.name} - {now.astimezone().strftime('%Y%m%d %H:%M')}",
        country_code=source_task.country_code,
        asset_type=source_task.asset_type,
        asset_identifier=source_task.asset_identifier,
        asset_name=source_task.asset_name,
        ai_model_name=source_task.ai_model_name,
        ai_model_config=source_task.ai_model_config or {},
        note=source_task.note,
        status="queued",
        max_iterations=source_task.max_iterations,
        target_annual_return=source_task.target_annual_return,
        max_drawdown_limit=source_task.max_drawdown_limit,
        min_sharpe=source_task.min_sharpe,
        initial_capital=source_task.initial_capital,
        position_size=source_task.position_size,
        stop_loss=source_task.stop_loss,
        take_profit=source_task.take_profit,
        min_add_position_interval=source_task.min_add_position_interval,
        max_holding_days=source_task.max_holding_days,
        backtest_start_date=source_task.backtest_start_date,
        backtest_end_date=source_task.backtest_end_date,
        created_at=now,
        updated_at=now,
    )
    db.session.add(task)
    db.session.flush()
    return task


def _save_top_strategies_for_run(run: ScheduledPlanRun) -> list[int]:
    plan = run.plan
    task = run.generated_agent_task
    if not plan or not task:
        return []

    score_weights = get_performance_score_weights(task.user)
    iterations = AgentIteration.query.filter(
        AgentIteration.task_id == task.id,
        AgentIteration.status == "success",
    ).all()
    ranked: list[tuple[float, AgentIteration]] = []
    for iteration in iterations:
        score = _score_iteration(iteration, weights=score_weights)
        if score is None:
            continue
        if plan.score_threshold_enabled and plan.score_threshold is not None and score < float(plan.score_threshold):
            continue
        ranked.append((score, iteration))

    ranked.sort(
        key=lambda item: (
            item[0],
            float(item[1].annual_return or 0),
            -float(item[1].max_drawdown or 0),
            item[1].iteration_number,
        ),
        reverse=True,
    )

    saved_ids: list[int] = []
    for score, iteration in ranked[: plan.save_top_n]:
        strategy = create_strategy(
            task.user,
            {
                "name": f"{plan.name} - 第 {iteration.iteration_number} 轮策略",
                "type": "AI Agent",
                "source": "计划任务",
                "countryRegion": task.country_code,
                "assetType": task.asset_type,
                "assetIdentifier": task.asset_identifier,
                "assetName": task.asset_name,
                "strategyConfig": iteration.strategy_config,
                "annualReturn": iteration.annual_return,
                "maxDrawdown": iteration.max_drawdown,
            },
        )
        saved_ids.append(strategy.id)
        try:
            evaluate_strategy(task.user, strategy.id)
        except Exception as exc:  # noqa: BLE001
            log_event(
                user=task.user,
                task_id=run.generated_agent_task.celery_task_id,
                event_type="backtest",
                event_name="scheduled_plan_evaluation_failed",
                source=plan.name,
                target=strategy.name,
                status="failed",
                level="warning",
                message=f"计划保存策略后提交回测评估失败：{exc}",
            )
        log_event(
            user=task.user,
            task_id=run.generated_agent_task.celery_task_id,
            event_type="agent",
            event_name="scheduled_plan_strategy_saved",
            source=plan.name,
            target=strategy.name,
            status="success",
            level="info",
            message=f"{plan.name} 已保存第 {iteration.iteration_number} 轮策略，综合分 {score:.2f}。",
        )
    return saved_ids


def _record_plan_failure(plan: ScheduledPlan, message: str, *, commit: bool = True) -> None:
    plan.failure_count = int(plan.failure_count or 0) + 1
    plan.last_error_message = message[:512]
    plan.updated_at = datetime.now(timezone.utc)
    if plan.failure_count >= INTERNAL_MAX_FAILURES:
        plan.status = "paused_failed"
        plan.next_run_at = None
    elif plan.status == "enabled":
        plan.next_run_at = calculate_next_run_at(plan, after=plan.updated_at)
    if commit:
        db.session.commit()


def _parse_int(value, label: str) -> int:
    try:
        return int(value)
    except Exception as exc:  # noqa: BLE001
        raise ScheduledPlanError(f"{label}格式无效。") from exc


def _parse_decimal(value, label: str) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception as exc:  # noqa: BLE001
        raise ScheduledPlanError(f"{label}格式无效。") from exc


def _parse_time(value) -> time:
    text = str(value or "").strip()
    try:
        hour, minute = text.split(":")[:2]
        return time(hour=int(hour), minute=int(minute))
    except Exception as exc:  # noqa: BLE001
        raise ScheduledPlanError("请选择有效的执行时间。") from exc


def _parse_int_list(value, minimum: int, maximum: int, label: str) -> list[int]:
    if not isinstance(value, list):
        return []
    result: list[int] = []
    for item in value:
        parsed = _parse_int(item, label)
        if minimum <= parsed <= maximum:
            result.append(parsed)
    return sorted(set(result))


def _acquire_lock(key: str, seconds: int) -> bool:
    if not redis_client:
        return True
    return bool(redis_client.set(key, "1", nx=True, ex=seconds))


def _release_lock(key: str) -> None:
    if redis_client:
        redis_client.delete(key)
