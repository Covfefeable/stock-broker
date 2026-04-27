from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

from app.models.strategy import Strategy
from app.models.strategy_evaluation import StrategyEvaluation
from app.models.user import User
from app.services.llm import AIClientError, call_chat_completion_json
from app.services.backtest_lab.errors import BacktestLabError
from app.services.backtest_lab.target_selection import get_default_ai_model_config, strategy_country_code
from app.services.strategies import (
    EXPRESSION_FUNCTION_ARITY,
    EXPRESSION_OPERATOR_VALUES,
    RULE_FIELD_VALUES,
    RULE_OPERATOR_VALUES,
    _validate_strategy_config,
)


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

