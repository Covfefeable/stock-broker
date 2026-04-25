from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sqlalchemy import desc, or_

from app.extensions import db
from app.models.agent_iteration import AgentIteration
from app.models.agent_task import AgentTask
from app.models.index_asset import IndexAsset
from app.models.stock import Stock
from app.models.user import User
from app.services.data_center_service import log_event
from app.services.settings_service import get_or_create_settings
from app.services.strategy_service import (
    StrategyError,
    _load_asset_bars,
    _run_strategy_backtest,
    _validate_strategy_config as _validate_token_strategy_config,
    list_strategy_asset_options,
)


class AgentTaskError(ValueError):
    pass


RULE_FIELDS = [
    {"label": "收盘价", "value": "close", "description": "当日收盘成交价。"},
    {"label": "开盘价", "value": "open", "description": "当日开盘成交价。"},
    {"label": "最高价", "value": "high", "description": "当日最高成交价。"},
    {"label": "最低价", "value": "low", "description": "当日最低成交价。"},
    {"label": "成交量", "value": "volume", "description": "当日成交数量。"},
    {"label": "MA5", "value": "ma5", "description": "最近 5 个交易日收盘价的简单移动平均。"},
    {"label": "MA10", "value": "ma10", "description": "最近 10 个交易日收盘价的简单移动平均。"},
    {"label": "MA20", "value": "ma20", "description": "最近 20 个交易日收盘价的简单移动平均。"},
    {"label": "MA60", "value": "ma60", "description": "最近 60 个交易日收盘价的简单移动平均。"},
    {"label": "MA120", "value": "ma120", "description": "最近 120 个交易日收盘价的简单移动平均。"},
    {"label": "RSI14", "value": "rsi14", "description": "14 日相对强弱指标，通常在 0 到 100 之间。"},
    {"label": "MACD DIF", "value": "macd_dif", "description": "EMA12 与 EMA26 的差值。"},
    {"label": "MACD DEA", "value": "macd_dea", "description": "MACD DIF 的 9 周期 EMA。"},
    {"label": "KDJ K", "value": "kdj_k", "description": "KDJ 中较敏感的 K 值。"},
    {"label": "KDJ D", "value": "kdj_d", "description": "KDJ 中更平滑的 D 值。"},
    {"label": "BIAS(MA20)", "value": "bias_ma20", "description": "收盘价相对 MA20 的偏离率，口径为 close / MA20 - 1。"},
    {"label": "5日收益率", "value": "return_5d", "description": "close / close[-5] - 1。"},
    {"label": "20日收益率", "value": "return_20d", "description": "close / close[-20] - 1。"},
    {"label": "60日收益率", "value": "return_60d", "description": "close / close[-60] - 1。"},
    {"label": "量比(5日)", "value": "volume_ratio_5", "description": "当日成交量相对 5 日平均成交量的倍数。"},
    {"label": "量比(20日)", "value": "volume_ratio_20", "description": "当日成交量相对 20 日平均成交量的倍数。"},
    {"label": "ATR14", "value": "atr14", "description": "14 日平均真实波幅。"},
    {"label": "20日波动率", "value": "volatility_20d", "description": "最近 20 个交易日日收益率标准差，不做年化。"},
    {"label": "20日区间位置", "value": "close_pct_of_20d_range", "description": "收盘价位于最近 20 日高低区间中的相对位置。"},
    {"label": "60日区间位置", "value": "close_pct_of_60d_range", "description": "收盘价位于最近 60 日高低区间中的相对位置。"},
    {"label": "距20日高点", "value": "distance_to_20d_high", "description": "收盘价相对最近 20 日最高价的偏离率。"},
    {"label": "距20日低点", "value": "distance_to_20d_low", "description": "收盘价相对最近 20 日最低价的偏离率。"},
    {"label": "实体占比", "value": "body_pct", "description": "|close - open| / open。"},
    {"label": "上影线占比", "value": "upper_shadow_pct", "description": "上影线长度相对开盘价的比例。"},
    {"label": "下影线占比", "value": "lower_shadow_pct", "description": "下影线长度相对开盘价的比例。"},
    {"label": "向上跳空", "value": "gap_up", "description": "若开盘价高于前一日最高价则记为 1，否则为 0。"},
    {"label": "向下跳空", "value": "gap_down", "description": "若开盘价低于前一日最低价则记为 1，否则为 0。"},
    {"label": "持仓收益率", "value": "position_return", "description": "当前收盘价相对持仓成本的收益率。"},
    {"label": "持仓天数", "value": "holding_days", "description": "从首次建仓到当前 K 线为止已持有的交易日数。"},
]

RULE_OPERATORS = [
    {"label": "大于", "value": ">"},
    {"label": "大于等于", "value": ">="},
    {"label": "小于", "value": "<"},
    {"label": "小于等于", "value": "<="},
    {"label": "等于", "value": "=="},
    {"label": "不等于", "value": "!="},
    {"label": "上穿", "value": "cross_over"},
    {"label": "下穿", "value": "cross_under"},
]
RULE_FIELD_VALUES = {item["value"] for item in RULE_FIELDS}
RULE_OPERATOR_VALUES = {item["value"] for item in RULE_OPERATORS}
RULE_FUNCTIONS = [
    {"name": "abs", "args": "x", "description": "绝对值。"},
    {"name": "min", "args": "a, b", "description": "两个表达式取较小值。"},
    {"name": "max", "args": "a, b", "description": "两个表达式取较大值。"},
    {"name": "sum", "args": "x, n", "description": "最近 n 根 K 线的表达式求和。"},
    {"name": "avg", "args": "x, n", "description": "最近 n 根 K 线的表达式均值。"},
    {"name": "std", "args": "x, n", "description": "最近 n 根 K 线的表达式标准差。"},
    {"name": "highest", "args": "x, n", "description": "最近 n 根 K 线的表达式最大值。"},
    {"name": "lowest", "args": "x, n", "description": "最近 n 根 K 线的表达式最小值。"},
    {"name": "change", "args": "x, n", "description": "当前表达式值减去 n 根 K 线前的表达式值。"},
    {"name": "pct_change", "args": "x, n", "description": "当前表达式相对 n 根 K 线前的变化率。"},
]

AI_DSL_GENERATION_RETRY_COUNT = 3


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
    best_iteration = _get_best_iteration(task)
    task_payload["bestMaxDrawdown"] = (
        round(float(best_iteration.max_drawdown), 2)
        if best_iteration and best_iteration.max_drawdown is not None
        else None
    )
    return {
        "task": task_payload,
        "iterations": [_serialize_agent_iteration_detail(task, item) for item in task.iterations],
    }


def preview_agent_iteration(user: User, task_id: int, iteration_id: int) -> dict:
    task = get_agent_task(user, task_id)
    iteration = AgentIteration.query.filter(
        AgentIteration.id == iteration_id,
        AgentIteration.task_id == task.id,
    ).first()
    if not iteration:
        raise AgentTaskError("未找到对应的迭代记录。")

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
        raise AgentTaskError("当前标的没有可用于预览收益的历史日线数据。")

    return _run_strategy_backtest(bars, iteration.strategy_config or {})


def _get_best_iteration(task: AgentTask) -> AgentIteration | None:
    query = AgentIteration.query.filter(AgentIteration.task_id == task.id)
    if task.best_annual_return is not None:
        query = query.filter(AgentIteration.annual_return == task.best_annual_return)
    return query.order_by(AgentIteration.iteration_number.desc(), AgentIteration.id.desc()).first()


def _serialize_agent_iteration_detail(task: AgentTask, iteration: AgentIteration) -> dict:
    payload = iteration.to_dict()
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
            "maxHoldingDays": task.max_holding_days,
            "backtestStartDate": task.backtest_start_date.isoformat(),
            "backtestEndDate": task.backtest_end_date.isoformat(),
        },
    )


def get_agent_task_asset_options(country_code: str, asset_type: str) -> dict:
    try:
        return list_strategy_asset_options(country_code, asset_type)
    except Exception as exc:  # noqa: BLE001
        raise AgentTaskError(str(exc)) from exc


def run_agent_iterations(task: AgentTask, *, task_id: str | None = None) -> dict:
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

    benchmark_preview = _run_strategy_backtest(bars, _build_noop_strategy_config(task))
    benchmark_metrics = {
        "benchmarkReturn": benchmark_preview["benchmarkReturn"],
        "benchmarkAnnualReturn": benchmark_preview["benchmarkAnnualReturn"],
        "benchmarkMaxDrawdown": benchmark_preview["benchmarkMaxDrawdown"],
        "benchmarkSharpe": benchmark_preview["benchmarkSharpe"],
        "benchmarkVolatility": benchmark_preview["benchmarkVolatility"],
    }

    best_result: dict | None = None
    recent_memories = [
        item.memory
        for item in reversed(task.iterations[-5:])
        if getattr(item, "memory", None)
    ]

    for iteration in range(1, task.max_iterations + 1):
        generation_result = _generate_strategy_with_ai(task, recent_memories, benchmark_metrics)
        strategy_config = generation_result["strategyConfig"]
        preview = _run_strategy_backtest(bars, strategy_config)
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
        summary = _build_iteration_summary(
            task,
            iteration,
            strategy_config,
            preview,
            best_result,
            benchmark_metrics,
            analysis_text,
            action_plan_text,
        )
        memory_text = _build_iteration_memory(
            iteration,
            strategy_config,
            preview,
            benchmark_metrics,
            analysis_text,
            action_plan_text,
            summary,
        )

        iteration_row = AgentIteration(
            task_id=task.id,
            iteration_number=iteration,
            status="success",
            annual_return=Decimal(str(preview["annualReturn"])),
            max_drawdown=Decimal(str(preview["maxDrawdown"])),
            sharpe=Decimal(str(preview["sharpe"])),
            strategy_config=strategy_config,
            memory=memory_text,
            analysis=analysis_text,
            action_plan=action_plan_text,
            summary=summary,
        )
        db.session.add(iteration_row)

        if _is_better_result(preview, best_result):
            best_result = preview
            task.best_annual_return = Decimal(str(preview["annualReturn"]))
            task.best_sharpe = Decimal(str(preview["sharpe"]))
            task.best_strategy_config = strategy_config
            task.best_summary = summary

        recent_memories.append(memory_text)
        recent_memories = recent_memories[-5:]

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
            message=f"第 {iteration}/{task.max_iterations} 轮完成：年化 {preview['annualReturn']:.2f}% / Sharpe {preview['sharpe']:.2f}。{summary}",
            records_affected=iteration,
        )

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


def _generate_strategy_with_ai(task: AgentTask, recent_memories: list[str], benchmark_metrics: dict[str, float]) -> dict:
    model_config = task.ai_model_config or {}
    if not model_config.get("baseUrl") or not model_config.get("apiKey") or not model_config.get("model"):
        raise AgentTaskError("Agent 任务缺少有效的 AI 模型配置。")

    prompt = _build_generation_prompt(task, recent_memories, benchmark_metrics)
    last_error: AgentTaskError | None = None

    for attempt in range(1, AI_DSL_GENERATION_RETRY_COUNT + 1):
        payload = {
            "model": model_config["model"],
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是一名量化研究员，负责为单一股票或指数生成可执行的 JSON 策略 DSL。"
                        "只能返回 JSON，不要包含 markdown，不要输出解释。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "response_format": {"type": "json_object"},
        }

        request = Request(
            f"{str(model_config['baseUrl']).rstrip('/')}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {model_config['apiKey']}",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=60) as response:
                raw_payload = json.loads(response.read().decode("utf-8"))
            content = (
                raw_payload.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            if not content:
                raise AgentTaskError("AI 模型没有返回策略内容。")

            generation_payload = _parse_strategy_generation_payload(content)
            strategy_config = generation_payload["strategyConfig"]
            _validate_strategy_config(strategy_config)
            return generation_payload
        except HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8")
            except Exception:  # noqa: BLE001
                detail = f"HTTP {exc.code}"
            last_error = AgentTaskError(f"AI 模型调用失败：{detail}")
        except URLError as exc:
            last_error = AgentTaskError(f"AI 模型网络异常：{exc.reason}")
        except AgentTaskError as exc:
            last_error = exc

    raise AgentTaskError(
        f"AI 连续 {AI_DSL_GENERATION_RETRY_COUNT} 次生成 DSL 失败，最后一次原因：{last_error}"
    )


def _build_generation_prompt(task: AgentTask, recent_memories: list[str], benchmark_metrics: dict[str, float]) -> str:
    memory_block = "\n".join(f"- {item}" for item in recent_memories) if recent_memories else "- 暂无历史记忆"
    return f"""
请围绕单一标的生成一套策略 JSON DSL，并采用 ReAct 风格：先分析，再决策，最后输出策略。

任务信息：
- 标的名称：{task.asset_name}
- 标的标识：{task.asset_identifier}
- 国家/地区：{task.country_code}
- 标的类型：{task.asset_type}
- 目标年化收益率：{float(task.target_annual_return):.2f}%
- 最大可接受回撤：{float(task.max_drawdown_limit):.2f}%
- 最低 Sharpe：{float(task.min_sharpe):.2f}

持续持有对照（从回测开始日开盘买入并一直持有到结束）：
- 持续持有总收益：{benchmark_metrics["benchmarkReturn"]:.2f}%
- 持续持有年化收益：{benchmark_metrics["benchmarkAnnualReturn"]:.2f}%
- 持续持有最大回撤：{benchmark_metrics["benchmarkMaxDrawdown"]:.2f}%
- 持续持有 Sharpe：{benchmark_metrics["benchmarkSharpe"]:.2f}
- 持续持有波动率：{benchmark_metrics["benchmarkVolatility"]:.2f}%

可用字段：
{json.dumps(RULE_FIELDS, ensure_ascii=False)}

可用运算符：
{json.dumps(RULE_OPERATORS, ensure_ascii=False)}

可用函数：
{json.dumps(RULE_FUNCTIONS, ensure_ascii=False)}

风险参数必须固定为：
{json.dumps({
    "initialCapital": float(task.initial_capital),
    "positionSize": float(task.position_size),
    "stopLoss": float(task.stop_loss),
    "takeProfit": float(task.take_profit),
    "maxHoldingDays": task.max_holding_days,
    "forceCloseOnEnd": True,
    "backtestStartDate": task.backtest_start_date.isoformat(),
    "backtestEndDate": task.backtest_end_date.isoformat(),
}, ensure_ascii=False)}

最近几轮记忆：
{memory_block}

返回 JSON，结构必须为：
{{
  "analysis": "先对当前标的、目标收益、持续持有对照、最近几轮记忆做简短分析",
  "actionPlan": "这一轮准备怎样调整 DSL、为什么这样调",
  "strategy": {{
    "entry": {{
      "type": "group",
      "logic": "and" 或 "or",
      "children": [ 条件或子组 ]
    }},
    "exit": {{
      "type": "group",
      "logic": "and" 或 "or",
      "children": [ 条件或子组 ]
    }},
    "risk": {{
      "initialCapital": number,
      "positionSize": number,
      "stopLoss": number,
      "takeProfit": number,
      "maxHoldingDays": number,
      "backtestStartDate": "YYYY-MM-DD",
      "backtestEndDate": "YYYY-MM-DD"
    }}
  }}
}}

条件节点格式：
{{
  "type": "condition",
  "leftExpression": [
    {{"type": "variable", "name": "close"}}
  ],
  "operator": ">",
  "rightExpression": [
    {{
      "type": "function",
      "name": "highest",
      "args": [
        [{{"type": "variable", "name": "close"}}],
        [{{"type": "number", "value": 60}}]
      ]
    }}
  ]
}}

表达式 token 只能使用：
- {{"type": "variable", "name": "close", "offset": -1}}，offset 可省略，且必须 <= 0
- {{"type": "number", "value": 20}}
- {{"type": "operator", "value": "+"}}，value 只能是 + - * /
- {{"type": "groupStart"}} 和 {{"type": "groupEnd"}}
- {{"type": "function", "name": "avg", "args": [[表达式 tokens], [{{"type": "number", "value": 20}}]]}}

要求：
- 买入规则里不要使用持仓收益率和持仓天数
- 不允许引用未来数据，任何变量 offset 都必须小于等于 0
- 窗口函数的窗口参数 n 必须是正整数数字 token
- 可以选择简单规则或复杂规则，不要被固定模板束缚
- 可以尝试趋势、突破、反转、动量、震荡过滤等不同思路
- 条件数量建议 1 到 6 个，必要时允许使用嵌套条件组
- 规则需要可读、合理，不要返回空 children
- 必须比较“策略目标”和“持续持有对照”，避免生成明显弱于持续持有的平庸策略
- 只输出 JSON 本身
""".strip()


def _parse_strategy_generation_payload(content: str) -> dict[str, str | dict]:
    normalized = content.strip()
    if normalized.startswith("```"):
        normalized = normalized.strip("`")
        normalized = normalized.replace("json", "", 1).strip()
    try:
        data = json.loads(normalized)
    except json.JSONDecodeError as exc:
        raise AgentTaskError("AI 返回的策略 DSL 不是合法 JSON。") from exc
    if not isinstance(data, dict):
        raise AgentTaskError("AI 返回的策略 DSL 结构无效。")
    strategy = data.get("strategy", data)
    if not isinstance(strategy, dict):
        raise AgentTaskError("AI 返回的策略 DSL 结构无效。")
    return {
        "analysis": str(data.get("analysis", "")).strip(),
        "actionPlan": str(data.get("actionPlan", "")).strip(),
        "strategyConfig": strategy,
    }


def _validate_strategy_config(strategy_config: dict) -> None:
    try:
        _validate_token_strategy_config(strategy_config)
    except StrategyError as exc:
        raise AgentTaskError(f"AI 返回的策略 DSL 无效：{exc}") from exc


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


def _is_better_result(current: dict, best: dict | None) -> bool:
    if best is None:
        return True
    current_tuple = (current["annualReturn"], current["sharpe"], -current["maxDrawdown"])
    best_tuple = (best["annualReturn"], best["sharpe"], -best["maxDrawdown"])
    return current_tuple > best_tuple


def _build_iteration_summary(
    task: AgentTask,
    iteration: int,
    strategy_config: dict,
    preview: dict,
    previous_best: dict | None,
    benchmark_metrics: dict[str, float],
    analysis: str | None = None,
    action_plan: str | None = None,
) -> str:
    entry_desc = _describe_group(strategy_config.get("entry") or {})
    exit_desc = _describe_group(strategy_config.get("exit") or {})

    summary_parts = [
        f"本轮买入规则为“{entry_desc}”，卖出规则为“{exit_desc}”。",
        f"回测结果：年化收益 {preview['annualReturn']:.2f}% ，最大回撤 {preview['maxDrawdown']:.2f}% ，Sharpe {preview['sharpe']:.2f}。",
        f"持续持有对照：年化收益 {benchmark_metrics['benchmarkAnnualReturn']:.2f}% ，总收益 {benchmark_metrics['benchmarkReturn']:.2f}% 。",
    ]

    if analysis:
        summary_parts.append(f"模型分析：{analysis}")
    if action_plan:
        summary_parts.append(f"本轮决策：{action_plan}")

    if previous_best is None or _is_better_result(preview, previous_best):
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


def _build_iteration_memory(
    iteration: int,
    strategy_config: dict,
    preview: dict,
    benchmark_metrics: dict[str, float],
    analysis: str,
    action_plan: str,
    summary: str,
) -> str:
    return (
        f"第 {iteration} 轮："
        f"策略 DSL={json.dumps(strategy_config, ensure_ascii=False)}；"
        f"策略结果=年化 {preview['annualReturn']:.2f}% / 总收益 {preview['totalReturn']:.2f}% / 最大回撤 {preview['maxDrawdown']:.2f}% / Sharpe {preview['sharpe']:.2f}；"
        f"持续持有=年化 {benchmark_metrics['benchmarkAnnualReturn']:.2f}% / 总收益 {benchmark_metrics['benchmarkReturn']:.2f}% / 最大回撤 {benchmark_metrics['benchmarkMaxDrawdown']:.2f}% / Sharpe {benchmark_metrics['benchmarkSharpe']:.2f}；"
        f"分析={analysis}；"
        f"决策={action_plan}；"
        f"总结={summary}"
    )


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
    entry_desc = _describe_group(strategy_config.get("entry") or {})
    exit_desc = _describe_group(strategy_config.get("exit") or {})
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
            "maxHoldingDays": task.max_holding_days,
            "backtestStartDate": task.backtest_start_date.isoformat(),
            "backtestEndDate": task.backtest_end_date.isoformat(),
        },
    }


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


FIELD_LABELS_BY_VALUE = {item["value"]: item["label"] for item in RULE_FIELDS}
OPERATOR_LABELS = {item["value"]: item["label"] for item in RULE_OPERATORS}
