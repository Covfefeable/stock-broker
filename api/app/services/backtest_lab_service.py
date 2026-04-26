from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import json
from math import isnan, sqrt
import random
from typing import Any

from sqlalchemy import and_, func, or_

from app.extensions import db
from app.models.index_asset import IndexAsset
from app.models.index_daily_bar import IndexDailyBar
from app.models.stock import Stock
from app.models.stock_daily_bar import StockDailyBar
from app.models.strategy import Strategy
from app.models.strategy_evaluation import StrategyEvaluation
from app.models.user import User
from app.services.ai_client import AIClientError, call_chat_completion_json
from app.services.data_center_service import log_event
from app.services.performance_score import calculate_performance_score
from app.services.settings_service import get_or_create_settings, get_performance_score_weights
from app.services.strategy_service import (
    EXPRESSION_FUNCTION_ARITY,
    EXPRESSION_OPERATOR_VALUES,
    RULE_FIELD_VALUES,
    RULE_OPERATOR_VALUES,
    _load_asset_bars,
    _run_strategy_backtest,
    _validate_strategy_config,
)


class BacktestLabError(Exception):
    pass


EVALUATION_STATUS_LABELS = {
    "not_evaluated": "未评估",
    "evaluating": "评估中",
    "queued": "评估中",
    "running": "评估中",
    "success": "已完成",
    "failure": "失败",
}


def list_backtest_lab_strategies(
    user: User,
    *,
    keyword: str = "",
    source: str = "",
    evaluation_status: str = "",
    page: int = 1,
    page_size: int = 10,
) -> dict:
    query = Strategy.query.filter(Strategy.user_id == user.id)

    normalized_keyword = keyword.strip()
    if normalized_keyword:
        pattern = f"%{normalized_keyword}%"
        query = query.filter(or_(Strategy.name.ilike(pattern), Strategy.type.ilike(pattern), Strategy.source.ilike(pattern)))
    if source:
        query = query.filter(Strategy.source == source)

    if evaluation_status:
        if evaluation_status == "not_evaluated":
            query = query.outerjoin(StrategyEvaluation, StrategyEvaluation.strategy_id == Strategy.id).filter(
                StrategyEvaluation.id.is_(None)
            )
        elif evaluation_status == "evaluating":
            query = query.join(StrategyEvaluation, StrategyEvaluation.strategy_id == Strategy.id).filter(
                StrategyEvaluation.user_id == user.id,
                StrategyEvaluation.status.in_(("queued", "running")),
            )
        else:
            query = query.join(StrategyEvaluation, StrategyEvaluation.strategy_id == Strategy.id).filter(
                StrategyEvaluation.user_id == user.id,
                StrategyEvaluation.status == evaluation_status,
            )

    query = query.order_by(Strategy.updated_at.desc())
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    evaluations = {
        item.strategy_id: item
        for item in StrategyEvaluation.query.filter(
            StrategyEvaluation.user_id == user.id,
            StrategyEvaluation.strategy_id.in_([strategy.id for strategy in items] or [0]),
        ).all()
    }

    source_options = [
        value
        for value in db.session.query(Strategy.source)
        .filter(Strategy.user_id == user.id)
        .distinct()
        .order_by(Strategy.source.asc())
        .all()
    ]

    return {
        "items": [backtest_lab_strategy_to_dict(strategy, evaluations.get(strategy.id)) for strategy in items],
        "pagination": {"page": page, "pageSize": page_size, "total": total},
        "filters": {
            "sources": [value for (value,) in source_options if value],
            "evaluationStatuses": ["not_evaluated", "evaluating", "success", "failure"],
        },
    }


def evaluate_strategy(user: User, strategy_id: int, selected_asset_identifiers: list[str] | None = None) -> StrategyEvaluation:
    strategy = Strategy.query.filter(Strategy.id == strategy_id, Strategy.user_id == user.id).first()
    if not strategy:
        raise BacktestLabError("未找到对应的策略。")
    if not strategy.asset_type or not strategy.asset_identifier:
        raise BacktestLabError("策略缺少原始标的信息，无法执行全面评估。")

    if selected_asset_identifiers is None:
        cross_asset_targets, selection_meta = select_cross_asset_targets_for_auto(user, strategy)
    else:
        cross_asset_targets = resolve_selected_cross_asset_targets(strategy, selected_asset_identifiers)
        selection_meta = {"mode": "manual", "message": "使用用户手动选择的跨标的样本。"}

    now = datetime.now(timezone.utc)
    evaluation = StrategyEvaluation.query.filter_by(user_id=user.id, strategy_id=strategy.id).first()
    if not evaluation:
        evaluation = StrategyEvaluation(user_id=user.id, strategy_id=strategy.id)
        db.session.add(evaluation)

    evaluation.status = "queued"
    evaluation.score = None
    evaluation.conclusion = None
    evaluation.generality_conclusion = None
    evaluation.stability_conclusion = None
    evaluation.risk_conclusion = None
    evaluation.summary = None
    evaluation.error_message = None
    evaluation.report = {
        "crossAssetSelection": selection_meta,
        "selectedCrossAssetTargets": cross_asset_targets,
    }
    evaluation.strategy_snapshot = strategy.to_dict()
    evaluation.started_at = None
    evaluation.finished_at = None
    evaluation.updated_at = now
    db.session.commit()

    from app.tasks.backtest_lab import run_strategy_evaluation_task

    async_result = run_strategy_evaluation_task.delay(evaluation_id=evaluation.id, user_id=user.id)
    evaluation.celery_task_id = async_result.id
    evaluation.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    log_event(
        user=user,
        task_id=async_result.id,
        event_type="backtest",
        event_name="strategy_evaluation_enqueued",
        source=strategy.name,
        target=strategy.asset_name or strategy.asset_identifier,
        status="queued",
        level="info",
        message=f"{strategy.name} 的全面评估任务已提交。",
    )
    return evaluation


def get_strategy_evaluation_detail(user: User, strategy_id: int) -> dict:
    strategy = Strategy.query.filter(Strategy.id == strategy_id, Strategy.user_id == user.id).first()
    if not strategy:
        raise BacktestLabError("未找到对应的策略。")
    evaluation = StrategyEvaluation.query.filter_by(user_id=user.id, strategy_id=strategy.id).first()
    return {
        "strategy": backtest_lab_strategy_to_dict(strategy, evaluation),
        "evaluation": evaluation.to_dict() if evaluation else None,
    }


def run_strategy_evaluation(evaluation: StrategyEvaluation, *, task_id: str | None = None) -> dict:
    strategy = evaluation.strategy
    if not strategy:
        raise BacktestLabError("评估任务缺少策略。")

    started_at = datetime.now(timezone.utc)
    evaluation.status = "running"
    evaluation.celery_task_id = task_id or evaluation.celery_task_id
    evaluation.started_at = started_at
    evaluation.updated_at = started_at
    db.session.commit()
    log_event(
        user=evaluation.user,
        task_id=task_id,
        event_type="backtest",
        event_name="strategy_evaluation_running",
        source=strategy.name,
        target=strategy.asset_name or strategy.asset_identifier,
        status="running",
        level="info",
        message=f"{strategy.name} 开始全面评估：跨标的、跨时间区间与交易健康度。",
    )

    report = build_strategy_evaluation_report(strategy, evaluation.id, evaluation.report or {})
    score = Decimal(str(report["score"]))
    evaluation.status = "success"
    evaluation.score = score
    evaluation.conclusion = report["conclusion"]
    evaluation.generality_conclusion = report["generality"]["conclusion"]
    evaluation.stability_conclusion = report["stability"]["conclusion"]
    evaluation.risk_conclusion = report["tradeHealth"]["conclusion"]
    evaluation.summary = report["summary"]
    evaluation.report = report
    evaluation.error_message = None
    evaluation.finished_at = datetime.now(timezone.utc)
    evaluation.updated_at = evaluation.finished_at
    db.session.commit()

    log_event(
        user=evaluation.user,
        task_id=task_id,
        event_type="backtest",
        event_name="strategy_evaluation_finished",
        source=strategy.name,
        target=strategy.asset_name or strategy.asset_identifier,
        status="success",
        level="info",
        message=f"{strategy.name} 全面评估完成，综合评分 {report['score']:.2f}，结论：{report['conclusion']}。",
    )
    return {"evaluationId": evaluation.id, "score": report["score"], "conclusion": report["conclusion"]}


def mark_strategy_evaluation_failed(evaluation: StrategyEvaluation, message: str, *, task_id: str | None = None) -> None:
    evaluation.status = "failure"
    evaluation.error_message = message
    evaluation.finished_at = datetime.now(timezone.utc)
    evaluation.updated_at = evaluation.finished_at
    db.session.commit()
    log_event(
        user=evaluation.user,
        task_id=task_id or evaluation.celery_task_id,
        event_type="backtest",
        event_name="strategy_evaluation_failed",
        source=evaluation.strategy.name if evaluation.strategy else "策略评估",
        target=evaluation.strategy.asset_name if evaluation.strategy else None,
        status="failed",
        level="error",
        message=message,
    )


def build_strategy_evaluation_report(strategy: Strategy, evaluation_id: int, evaluation_payload: dict | None = None) -> dict:
    rng = random.Random(f"strategy-evaluation:{strategy.id}:{evaluation_id}")
    country_code = strategy_country_code(strategy)
    score_weights = get_performance_score_weights(strategy.user)
    original_asset = {
        "assetType": strategy.asset_type,
        "assetIdentifier": strategy.asset_identifier,
        "assetName": strategy.asset_name,
        "countryCode": country_code,
    }

    cross_asset_targets = list((evaluation_payload or {}).get("selectedCrossAssetTargets") or [])
    if not cross_asset_targets:
        cross_asset_targets = select_cross_asset_targets(strategy, rng)
    cross_asset_results = [run_target_evaluation(strategy, target, score_weights=score_weights) for target in cross_asset_targets]

    time_ranges = select_time_ranges(strategy, rng)
    time_results = [
        run_target_evaluation(
            strategy,
            {
                "assetType": strategy.asset_type,
                "assetIdentifier": strategy.asset_identifier,
                "assetName": strategy.asset_name,
                "countryCode": country_code,
                "rangeLabel": item["label"],
                "startDate": item["startDate"],
                "endDate": item["endDate"],
            },
            score_weights=score_weights,
        )
        for item in time_ranges
    ]

    full_original = run_target_evaluation(strategy, original_asset, score_weights=score_weights)
    generality = summarize_result_group(cross_asset_results, "跨标的通用性")
    stability = summarize_result_group(time_results, "跨时间区间稳定性")
    trade_health = summarize_trade_health([full_original, *cross_asset_results, *time_results])
    score = calculate_evaluation_score(generality, stability, trade_health)
    conclusion = score_to_conclusion(score)
    summary = (
        f"跨标的通过率 {generality['passRate']:.2f}%，跨时间通过率 {stability['passRate']:.2f}%，"
        f"交易健康度 {trade_health['score']:.2f}。综合判断：{conclusion}。"
    )
    ai_advice = generate_evaluation_ai_advice(
        strategy,
        {
            "score": round(score, 2),
            "conclusion": conclusion,
            "summary": summary,
            "fullOriginal": full_original,
            "generality": generality,
            "stability": stability,
            "tradeHealth": trade_health,
            "crossAssetResults": cross_asset_results,
            "timeRangeResults": time_results,
        },
    )

    return {
        "score": round(score, 2),
        "conclusion": conclusion,
        "summary": summary,
        "aiAdvice": ai_advice,
        "originalAsset": original_asset,
        "fullOriginal": full_original,
        "generality": generality,
        "stability": stability,
        "tradeHealth": trade_health,
        "crossAssetResults": cross_asset_results,
        "timeRangeResults": time_results,
        "crossAssetSelection": (evaluation_payload or {}).get("crossAssetSelection") or {},
    }


def generate_evaluation_ai_advice(strategy: Strategy, report: dict) -> dict:
    model_config = get_default_ai_model_config(strategy.user)
    if not model_config:
        return {
            "status": "skipped",
            "message": "当前没有可用 AI 模型，暂未生成 AI 建议。",
        }

    prompt_payload = {
        "strategy": {
            "name": strategy.name,
            "type": strategy.type,
            "assetType": strategy.asset_type,
            "assetIdentifier": strategy.asset_identifier,
            "assetName": strategy.asset_name,
            "countryRegion": strategy.country_region,
            "strategyConfig": strategy.strategy_config or {},
        },
        "evaluation": {
            "score": report.get("score"),
            "conclusion": report.get("conclusion"),
            "summary": report.get("summary"),
            "fullOriginal": report.get("fullOriginal"),
            "generality": report.get("generality"),
            "stability": report.get("stability"),
            "tradeHealth": report.get("tradeHealth"),
            "crossAssetResults": report.get("crossAssetResults"),
            "timeRangeResults": report.get("timeRangeResults"),
        },
        "scoreMethod": "评估总分综合跨标的得分、跨时间得分、回撤风险与交易健康度；单样本综合分使用系统设置中的评分权重。",
    }
    prompt = (
        "你是量化策略评估顾问。请基于策略买入/卖出规则、跨标的评估、跨时间区间评估、交易健康度和评分信息，"
        "给出面向研究人员的评估建议。必须返回合法 JSON，不要 markdown。字段："
        "{\"ruleAnalysis\":\"买入卖出规则解析\",\"riskPoints\":[\"潜在风险点\"],\"recommendation\":\"综合建议\"}。\n"
        f"评估材料：{json.dumps(prompt_payload, ensure_ascii=False)}"
    )
    try:
        parsed = call_chat_completion_json(
            model_config,
            [
                {"role": "system", "content": "你只能返回合法 JSON，不要输出 markdown。"},
                {"role": "user", "content": prompt},
            ],
            timeout=180,
            temperature=0.25,
        )
    except AIClientError as exc:
        return {
            "status": "failed",
            "message": f"AI 建议生成失败：{exc}",
        }

    return {
        "status": "success",
        "ruleAnalysis": str(parsed.get("ruleAnalysis") or "").strip(),
        "riskPoints": [str(item).strip() for item in parsed.get("riskPoints") or [] if str(item).strip()],
        "recommendation": str(parsed.get("recommendation") or "").strip(),
    }


def generate_improved_strategy(user: User, strategy_id: int) -> dict:
    strategy = Strategy.query.filter(Strategy.id == strategy_id, Strategy.user_id == user.id).first()
    if not strategy:
        raise BacktestLabError("未找到对应的策略。")
    evaluation = StrategyEvaluation.query.filter_by(user_id=user.id, strategy_id=strategy.id).first()
    if not evaluation or evaluation.status != "success":
        raise BacktestLabError("请先完成策略评估，再生成更优策略。")

    model_config = get_default_ai_model_config(user)
    if not model_config:
        raise BacktestLabError("当前没有可用 AI 模型，请先在系统设置中配置默认模型。")

    report = evaluation.report or {}
    prompt_payload = {
        "currentStrategy": {
            "name": strategy.name,
            "type": strategy.type,
            "countryCode": strategy_country_code(strategy),
            "assetType": strategy.asset_type,
            "assetIdentifier": strategy.asset_identifier,
            "assetName": strategy.asset_name,
            "strategyConfig": strategy.strategy_config or {},
        },
        "evaluation": _compact_report_for_ai(report),
        "aiAdvice": report.get("aiAdvice") or {},
        "requirements": {
            "source": "人工创建",
            "sameAssetOnly": True,
            "changePolicy": "只允许基于当前策略做微调，不允许重写成全新结构；必须先保留当前策略在评估中体现出的优势，再针对劣势做小步修补；优先保留原买入/卖出规则的主体结构、指标族和风控参数，只根据 aiAdvice 中的风险点与综合建议调整 1 到 3 个核心点。",
            "allowedRuleFields": sorted(RULE_FIELD_VALUES),
            "allowedRuleOperators": sorted(RULE_OPERATOR_VALUES),
            "allowedExpressionOperators": sorted(EXPRESSION_OPERATOR_VALUES),
            "allowedFunctions": sorted(EXPRESSION_FUNCTION_ARITY.keys()),
            "strictRule": "只能使用 allowedRuleFields 中的变量；禁止使用 ADX、ADX14、EMA、布林带等未列出的字段；如需趋势强度，只能用 ma、return、volatility、atr、range position 等已有字段组合表达。",
            "output": {
                "name": "新策略名称",
                "type": "策略类型，限定为动量/趋势/价值/事件驱动/低波动/成长/资产配置之一",
                "strategyConfig": "完整规则 DSL，必须包含 entry、exit、risk",
            },
        },
    }
    prompt = (
        "你是量化策略微调专家。请结合当前页面里的评估数据、AI 总结、买入卖出规则、跨标的与跨时间表现，"
        "生成一个小幅优化后的新策略草稿。新策略仍运行在相同国家、相同股票/指数标的上，只优化名称、类型和规则 DSL。"
        "不要大改、不要重写成全新策略；必须以当前策略为主体，保留原来的核心指标族、主要买入卖出结构和风控框架。"
        "必须先从评估数据中判断当前策略的优势，并保留这些优势；再针对评估中暴露的劣势做补强，不能为了修补劣势牺牲已有优势。"
        "只允许根据 aiAdvice 中的规则解析、潜在风险点、综合建议微调 1 到 3 个核心点，例如略微放宽/收紧阈值、增加一个轻量过滤条件、调整止盈止损或最大持仓天数。"
        "如果评估中暴露跨时间失效、交易次数过低或过高、回撤过大、买入持有基准对比弱，也只能做针对这些问题的小步修正。"
        "规则 DSL 只能使用材料 requirements.allowedRuleFields 里的变量，不能编造任何未列出的指标。"
        "必须返回合法 JSON，不要 markdown。格式："
        "{\"name\":\"...\",\"type\":\"趋势\",\"strategyConfig\":{...}}。\n"
        f"材料：{json.dumps(prompt_payload, ensure_ascii=False)}"
    )
    raw = call_ai_json(model_config, prompt, timeout=120, temperature=0.35)
    strategy_config = raw.get("strategyConfig")
    if not isinstance(strategy_config, dict):
        raise BacktestLabError("AI 返回的新策略规则格式无效。")
    try:
        _validate_strategy_config(strategy_config)
    except Exception as exc:
        retry_prompt = (
            f"{prompt}\n\n上一次返回的规则没有通过校验，错误是：{exc}。\n"
            "请只修正规则 DSL，不要使用任何未列入 allowedRuleFields 的变量，重新返回完整 JSON。"
        )
        raw = call_ai_json(model_config, retry_prompt, timeout=120, temperature=0.2)
        strategy_config = raw.get("strategyConfig")
        if not isinstance(strategy_config, dict):
            raise BacktestLabError("AI 返回的新策略规则格式无效。")
        try:
            _validate_strategy_config(strategy_config)
        except Exception as retry_exc:
            raise BacktestLabError(f"AI 返回的新策略规则无效：{retry_exc}") from retry_exc

    name = str(raw.get("name") or f"{strategy.name} 优化版").strip()
    strategy_type = str(raw.get("type") or strategy.type).strip()
    if strategy_type not in {"动量", "趋势", "价值", "事件驱动", "低波动", "成长", "资产配置"}:
        strategy_type = strategy.type if strategy.type in {"动量", "趋势", "价值", "事件驱动", "低波动", "成长", "资产配置"} else "趋势"

    return {
        "name": name,
        "type": strategy_type,
        "countryCode": strategy_country_code(strategy),
        "assetType": strategy.asset_type,
        "assetIdentifier": strategy.asset_identifier,
        "assetName": strategy.asset_name,
        "strategyConfig": strategy_config,
    }


def _compact_report_for_ai(report: dict) -> dict:
    def compact_result(item: dict) -> dict:
        return {
            key: item.get(key)
            for key in (
                "assetName",
                "assetIdentifier",
                "rangeLabel",
                "passed",
                "score",
                "benchmarkScore",
                "annualReturn",
                "benchmarkAnnualReturn",
                "maxDrawdown",
                "benchmarkMaxDrawdown",
                "sharpe",
                "benchmarkSharpe",
                "tradeCount",
                "winRate",
                "reason",
            )
            if key in item
        }

    return {
        "score": report.get("score"),
        "conclusion": report.get("conclusion"),
        "summary": report.get("summary"),
        "fullOriginal": compact_result(report.get("fullOriginal") or {}),
        "generality": report.get("generality"),
        "stability": report.get("stability"),
        "tradeHealth": report.get("tradeHealth"),
        "crossAssetResults": [compact_result(item) for item in report.get("crossAssetResults") or []],
        "timeRangeResults": [compact_result(item) for item in report.get("timeRangeResults") or []],
    }


def call_ai_json(model_config: dict, prompt: str, *, timeout: int, temperature: float) -> dict:
    try:
        return call_chat_completion_json(
            model_config,
            [
                {"role": "system", "content": "你只能返回合法 JSON，不要输出 markdown。"},
                {"role": "user", "content": prompt},
            ],
            timeout=timeout,
            temperature=temperature,
        )
    except AIClientError as exc:
        raise BacktestLabError(str(exc)) from exc


def select_cross_asset_targets(strategy: Strategy, rng: random.Random) -> list[dict]:
    targets = list_cross_asset_candidates(strategy)
    rng.shuffle(targets)
    return targets[:10]


def list_cross_asset_candidates(strategy: Strategy) -> list[dict]:
    country_code = strategy_country_code(strategy)
    if strategy.asset_type == "stock":
        latest_dates = (
            db.session.query(
                StockDailyBar.exchange_code.label("exchange_code"),
                StockDailyBar.ticker.label("ticker"),
                func.max(StockDailyBar.trade_date).label("latest_date"),
            )
            .group_by(StockDailyBar.exchange_code, StockDailyBar.ticker)
            .subquery()
        )
        rows = (
            db.session.query(Stock, latest_dates.c.latest_date)
            .join(latest_dates, and_(Stock.exchange_code == latest_dates.c.exchange_code, Stock.ticker == latest_dates.c.ticker))
            .filter(Stock.country_code == country_code)
            .order_by(Stock.exchange_code.asc(), Stock.ticker.asc())
            .all()
        )
        targets = [
            {
                "assetType": "stock",
                "assetIdentifier": f"{stock.exchange_code}:{stock.ticker}",
                "assetName": stock.name,
                "countryCode": stock.country_code,
                "latestDate": latest_date.isoformat() if latest_date else None,
            }
            for stock, latest_date in rows
            if f"{stock.exchange_code}:{stock.ticker}" != strategy.asset_identifier
        ]
    else:
        latest_dates = (
            db.session.query(
                IndexDailyBar.country_code.label("country_code"),
                IndexDailyBar.ticker.label("ticker"),
                func.max(IndexDailyBar.trade_date).label("latest_date"),
            )
            .group_by(IndexDailyBar.country_code, IndexDailyBar.ticker)
            .subquery()
        )
        rows = (
            db.session.query(IndexAsset, latest_dates.c.latest_date)
            .join(latest_dates, and_(IndexAsset.country_code == latest_dates.c.country_code, IndexAsset.ticker == latest_dates.c.ticker))
            .filter(IndexAsset.country_code == country_code)
            .order_by(IndexAsset.ticker.asc())
            .all()
        )
        targets = [
            {
                "assetType": "index",
                "assetIdentifier": item.ticker,
                "assetName": item.name,
                "countryCode": item.country_code,
                "latestDate": latest_date.isoformat() if latest_date else None,
            }
            for item, latest_date in rows
            if item.ticker != strategy.asset_identifier
        ]
    return targets


def list_evaluation_candidate_assets(user: User, strategy_id: int) -> dict:
    strategy = Strategy.query.filter(Strategy.id == strategy_id, Strategy.user_id == user.id).first()
    if not strategy:
        raise BacktestLabError("未找到对应的策略。")
    targets = list_cross_asset_candidates(strategy)
    return {
        "strategy": backtest_lab_strategy_to_dict(strategy, None),
        "countryCode": strategy_country_code(strategy),
        "assetType": strategy.asset_type,
        "items": [candidate_to_option(item) for item in targets],
    }


def select_candidate_assets_by_ai(user: User, strategy_id: int) -> dict:
    strategy = Strategy.query.filter(Strategy.id == strategy_id, Strategy.user_id == user.id).first()
    if not strategy:
        raise BacktestLabError("未找到对应的策略。")
    candidates = list_cross_asset_candidates(strategy)
    if not candidates:
        raise BacktestLabError("当前策略所在国家/地区没有其他已同步日线数据的同类型标的，无法执行跨标的评估。")
    model_config = get_default_ai_model_config(user)
    if not model_config:
        raise BacktestLabError("当前没有可用 AI 模型，请先在系统设置中配置默认模型。")
    targets = select_similar_assets_with_ai(strategy, candidates, model_config)
    if not targets:
        raise BacktestLabError("AI 未返回有效标的，请手动选择评估标的。")
    return {
        "items": [candidate_to_option(item) for item in targets],
        "selection": {"mode": "ai", "message": "已由默认 AI 模型选取风格类似的标的。"},
    }


def select_cross_asset_targets_for_auto(user: User, strategy: Strategy) -> tuple[list[dict], dict]:
    candidates = list_cross_asset_candidates(strategy)
    if not candidates:
        raise BacktestLabError("当前策略所在国家/地区没有其他已同步日线数据的同类型标的，无法执行跨标的评估。")
    if len(candidates) <= 10:
        return candidates, {"mode": "all", "message": "候选标的不足 10 个，已使用全部可用标的。"}

    model_config = get_default_ai_model_config(user)
    if not model_config:
        rng = random.Random(f"strategy-evaluation:fallback:{strategy.id}:{len(candidates)}")
        fallback = candidates[:]
        rng.shuffle(fallback)
        return fallback[:10], {"mode": "random", "message": "没有可用 AI 模型，已随机抽取 10 个有数据的标的。"}

    try:
        selected = select_similar_assets_with_ai(strategy, candidates, model_config)
        if selected:
            return selected[:10], {"mode": "ai", "message": "已由默认 AI 模型选取风格类似的 10 个标的。"}
    except BacktestLabError as exc:
        rng = random.Random(f"strategy-evaluation:ai-fallback:{strategy.id}:{len(candidates)}")
        fallback = candidates[:]
        rng.shuffle(fallback)
        return fallback[:10], {"mode": "random", "message": f"AI 选取失败，已随机抽取 10 个标的：{exc}"}

    rng = random.Random(f"strategy-evaluation:empty-ai:{strategy.id}:{len(candidates)}")
    fallback = candidates[:]
    rng.shuffle(fallback)
    return fallback[:10], {"mode": "random", "message": "AI 未返回有效标的，已随机抽取 10 个标的。"}


def resolve_selected_cross_asset_targets(strategy: Strategy, selected_asset_identifiers: list[str]) -> list[dict]:
    normalized = [str(item).strip() for item in selected_asset_identifiers if str(item).strip()]
    if not normalized:
        raise BacktestLabError("请选择至少一个用于重新评估的股票或指数。")
    candidates = {item["assetIdentifier"]: item for item in list_cross_asset_candidates(strategy)}
    missing = [item for item in normalized if item not in candidates]
    if missing:
        raise BacktestLabError("所选标的不存在或没有历史日线数据，请重新选择。")
    return [candidates[item] for item in normalized]


def candidate_to_option(item: dict) -> dict:
    latest_date = item.get("latestDate")
    return {
        "label": f"{item.get('assetIdentifier')} - {item.get('assetName') or '-'}"
        + (f"（同步至 {latest_date}）" if latest_date else ""),
        "value": item.get("assetIdentifier"),
        "name": item.get("assetName"),
        "assetIdentifier": item.get("assetIdentifier"),
        "latestDate": latest_date,
    }


def get_default_ai_model_config(user: User) -> dict | None:
    settings = get_or_create_settings(user)
    models = settings.ai_models or []
    if not models:
        return None
    first = models[0]
    model_config = {
        "name": str(first.get("name", "")).strip(),
        "model": str(first.get("model", "")).strip(),
        "baseUrl": str(first.get("baseUrl", "")).strip(),
        "apiKey": str(first.get("apiKey", "")).strip(),
    }
    if not model_config["model"] or not model_config["baseUrl"] or not model_config["apiKey"]:
        return None
    return model_config


def select_similar_assets_with_ai(strategy: Strategy, candidates: list[dict], model_config: dict) -> list[dict]:
    candidate_payload = [
        {
            "assetIdentifier": item["assetIdentifier"],
            "assetName": item.get("assetName"),
            "latestDate": item.get("latestDate"),
        }
        for item in candidates[:500]
    ]
    prompt = (
        "你是量化研究助理。请从候选标的里选择最多 10 个与原始策略标的风格尽可能类似、适合做跨标的评估的标的。"
        "只能从候选列表中选择，不要编造。返回 JSON：{\"assetIdentifiers\":[\"...\"]}。\n"
        f"原始标的：类型={strategy.asset_type}，代码={strategy.asset_identifier}，名称={strategy.asset_name or '-'}，"
        f"国家/地区={strategy.country_region}。\n"
        f"候选标的：{json.dumps(candidate_payload, ensure_ascii=False)}"
    )
    try:
        parsed = call_chat_completion_json(
            model_config,
            [
                {"role": "system", "content": "你只能返回合法 JSON，不要输出 markdown。"},
                {"role": "user", "content": prompt},
            ],
            timeout=120,
            temperature=0.2,
        )
    except AIClientError as exc:
        raise BacktestLabError(str(exc)) from exc

    identifiers = parsed.get("assetIdentifiers")
    if not isinstance(identifiers, list):
        return []
    candidate_map = {item["assetIdentifier"]: item for item in candidates}
    selected: list[dict] = []
    for identifier in identifiers:
        key = str(identifier).strip()
        if key in candidate_map and key not in {item["assetIdentifier"] for item in selected}:
            selected.append(candidate_map[key])
        if len(selected) >= 10:
            break
    return selected


def select_time_ranges(strategy: Strategy, rng: random.Random) -> list[dict]:
    bars = load_bars_for_range(strategy.asset_type or "", strategy.asset_identifier or "", strategy_country_code(strategy), strategy.strategy_config or {})
    if not bars:
        return []
    start_year = bars[0]["date"].year
    end_year = bars[-1]["date"].year
    recent_years = list(range(max(start_year, end_year - 4), end_year + 1))
    ranges: list[dict] = [
        {"label": f"{year} 年", "startDate": f"{year}-01-01", "endDate": f"{year}-12-31"}
        for year in recent_years
    ]

    for window, count in ((3, 3), (5, 2)):
        latest_start = end_year - window + 1
        earliest_start = max(start_year, latest_start - count + 1)
        for year in range(earliest_start, latest_start + 1):
            ranges.append(
                {
                    "label": f"{year}-{year + window - 1} 年",
                    "startDate": f"{year}-01-01",
                    "endDate": f"{year + window - 1}-12-31",
                }
            )
    return ranges


def strategy_country_code(strategy: Strategy) -> str:
    return str(strategy.country_region or "").split("-", 1)[0].strip().upper()


def run_target_evaluation(strategy: Strategy, target: dict, *, score_weights: dict[str, float] | None = None) -> dict:
    config = build_config_for_range(strategy.strategy_config or {}, target.get("startDate"), target.get("endDate"))
    try:
        bars = _load_asset_bars(target["assetType"], target["assetIdentifier"], target["countryCode"], config)
        if len(bars) < 60:
            return failed_result(target, "可用 K 线少于 60 条，跳过评估。")
        preview = _run_strategy_backtest(bars, config)
        strategy_score = calculate_performance_score(
            preview.get("annualReturn"),
            preview.get("sharpe"),
            preview.get("maxDrawdown"),
            weights=score_weights,
        )
        benchmark_score = calculate_performance_score(
            preview.get("benchmarkAnnualReturn"),
            preview.get("benchmarkSharpe"),
            preview.get("benchmarkMaxDrawdown"),
            weights=score_weights,
        )
        score_diff = strategy_score - benchmark_score
        sample_score = calculate_sample_score(strategy_score, benchmark_score)
        passed = result_passes(sample_score)
        return {
            **target,
            "status": "success",
            "passed": passed,
            "score": round(strategy_score, 2),
            "benchmarkScore": round(benchmark_score, 2),
            "scoreDiff": round(score_diff, 2),
            "sampleScore": sample_score,
            "reason": build_result_reason(preview, passed, strategy_score, benchmark_score, sample_score),
            "dateRange": preview.get("dateRange"),
            "annualReturn": preview.get("annualReturn"),
            "benchmarkAnnualReturn": preview.get("benchmarkAnnualReturn"),
            "totalReturn": preview.get("totalReturn"),
            "benchmarkReturn": preview.get("benchmarkReturn"),
            "maxDrawdown": preview.get("maxDrawdown"),
            "benchmarkMaxDrawdown": preview.get("benchmarkMaxDrawdown"),
            "sharpe": preview.get("sharpe"),
            "benchmarkSharpe": preview.get("benchmarkSharpe"),
            "tradeCount": preview.get("tradeCount"),
            "benchmarkTradeCount": preview.get("benchmarkTradeCount"),
            "winRate": preview.get("winRate"),
            "benchmarkWinRate": preview.get("benchmarkWinRate"),
            "volatility": preview.get("volatility"),
            "detail": preview,
        }
    except Exception as exc:  # noqa: BLE001
        return failed_result(target, str(exc))


def load_bars_for_range(asset_type: str, asset_identifier: str, country_code: str, strategy_config: dict) -> list[dict]:
    config = build_config_for_range(strategy_config, None, None)
    config.setdefault("risk", {}).pop("backtestStartDate", None)
    config.setdefault("risk", {}).pop("backtestEndDate", None)
    return _load_asset_bars(asset_type, asset_identifier, country_code, config)


def build_config_for_range(strategy_config: dict, start_date: str | None, end_date: str | None) -> dict:
    config = deepcopy(strategy_config)
    risk = config.setdefault("risk", {})
    if start_date:
        risk["backtestStartDate"] = start_date
    if end_date:
        risk["backtestEndDate"] = end_date
    return config


def failed_result(target: dict, message: str) -> dict:
    return {**target, "status": "failure", "passed": False, "reason": message}


def calculate_sample_score(strategy_score: float, benchmark_score: float) -> float:
    return round(min(max(50.0 + (strategy_score - benchmark_score) * 2.0, 0.0), 100.0), 2)


def result_passes(sample_score: float) -> bool:
    return sample_score >= 52.0


def build_result_reason(preview: dict, passed: bool, strategy_score: float, benchmark_score: float, sample_score: float) -> str:
    prefix = "通过" if passed else "未通过"
    return (
        f"{prefix}：样本分 {sample_score:.2f}，策略综合分 {strategy_score:.2f}，买入持有基准 {benchmark_score:.2f}；"
        f"年化 {preview.get('annualReturn')}%，买入持有基准 {preview.get('benchmarkAnnualReturn')}%，"
        f"回撤 {preview.get('maxDrawdown')}%，Sharpe {preview.get('sharpe')}，交易 {preview.get('tradeCount')} 次。"
    )


def summarize_result_group(results: list[dict], label: str) -> dict:
    total = len(results)
    success_rows = [item for item in results if item.get("status") == "success"]
    passed_rows = [item for item in success_rows if item.get("passed")]
    pass_rate = (len(passed_rows) / total * 100) if total else 0.0
    sample_scores = [float(item.get("sampleScore")) for item in success_rows if item.get("sampleScore") is not None]
    average_sample_score = average(sample_scores)
    sample_score_std = standard_deviation(sample_scores)
    group_score = max(0.0, min(100.0, average_sample_score - sample_score_std * 0.2)) if sample_scores else 0.0
    avg_annual = average([item.get("annualReturn") for item in success_rows])
    avg_drawdown = average([item.get("maxDrawdown") for item in success_rows])
    avg_sharpe = average([item.get("sharpe") for item in success_rows])
    conclusion = group_conclusion(group_score)
    return {
        "label": label,
        "total": total,
        "successCount": len(success_rows),
        "passedCount": len(passed_rows),
        "passRate": round(pass_rate, 2),
        "score": round(group_score, 2),
        "averageSampleScore": round(average_sample_score, 2),
        "sampleScoreStd": round(sample_score_std, 2),
        "averageAnnualReturn": avg_annual,
        "averageMaxDrawdown": avg_drawdown,
        "averageSharpe": avg_sharpe,
        "conclusion": conclusion,
        "warnings": [item for item in results if not item.get("passed")][:5],
    }


def summarize_trade_health(results: list[dict]) -> dict:
    success_rows = [item for item in results if item.get("status") == "success"]
    if not success_rows:
        return {"score": 0.0, "conclusion": "无有效样本", "averageTradeCount": 0.0, "warnings": ["没有可评估的交易样本。"]}
    trade_counts = [int(item.get("tradeCount") or 0) for item in success_rows]
    healthy_count = sum(1 for count in trade_counts if 2 <= count <= 120)
    score = healthy_count / len(success_rows) * 100
    warnings: list[str] = []
    too_low = sum(1 for count in trade_counts if count < 2)
    too_high = sum(1 for count in trade_counts if count > 120)
    if too_low:
        warnings.append(f"{too_low} 个样本交易次数过低，可能买卖条件过苛。")
    if too_high:
        warnings.append(f"{too_high} 个样本交易次数过高，可能噪音交易偏多。")
    return {
        "score": round(score, 2),
        "conclusion": group_conclusion(score),
        "averageTradeCount": round(sum(trade_counts) / len(trade_counts), 2),
        "warnings": warnings,
    }


def calculate_evaluation_score(generality: dict, stability: dict, trade_health: dict) -> float:
    risk_drawdown = max(
        float(generality.get("averageMaxDrawdown") or 0),
        float(stability.get("averageMaxDrawdown") or 0),
    )
    risk_score = max(0.0, 100.0 - risk_drawdown * 2)
    return (
        float(generality.get("score") or 0) * 0.25
        + float(stability.get("score") or 0) * 0.35
        + risk_score * 0.2
        + float(trade_health.get("score") or 0) * 0.1
    )


def score_to_conclusion(score: float) -> str:
    if score >= 75:
        return "已通过"
    if score >= 60:
        return "可观察"
    if score >= 45:
        return "风险较高"
    return "未通过"


def group_conclusion(score: float) -> str:
    if score >= 75:
        return "表现稳健"
    if score >= 60:
        return "基本可观察"
    if score >= 45:
        return "存在明显分化"
    return "稳定性不足"


def average(values: list[Any]) -> float:
    numbers = [float(value) for value in values if value is not None]
    if not numbers:
        return 0.0
    result = sum(numbers) / len(numbers)
    return 0.0 if isnan(result) else round(result, 2)


def standard_deviation(values: list[Any]) -> float:
    numbers = [float(value) for value in values if value is not None]
    if len(numbers) < 2:
        return 0.0
    mean = sum(numbers) / len(numbers)
    result = sqrt(sum((value - mean) ** 2 for value in numbers) / len(numbers))
    return 0.0 if isnan(result) else result


def backtest_lab_strategy_to_dict(strategy: Strategy, evaluation: StrategyEvaluation | None) -> dict:
    evaluation_payload = evaluation.to_dict() if evaluation else None
    status = evaluation.status if evaluation else "not_evaluated"
    return {
        "id": strategy.id,
        "name": strategy.name,
        "type": strategy.type,
        "source": strategy.source,
        "status": strategy.status,
        "countryRegion": strategy.country_region,
        "assetName": strategy.asset_name,
        "assetIdentifier": strategy.asset_identifier,
        "assetType": strategy.asset_type,
        "strategyConfig": strategy.strategy_config or {},
        "updatedAt": strategy.updated_at.isoformat() if strategy.updated_at else None,
        "evaluationStatus": status,
        "evaluationStatusLabel": EVALUATION_STATUS_LABELS.get(status, status),
        "evaluation": evaluation_payload,
    }
