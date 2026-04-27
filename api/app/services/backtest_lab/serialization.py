from __future__ import annotations

import random

from app.models.strategy import Strategy
from app.models.strategy_evaluation import StrategyEvaluation
from app.services.backtest_lab.ai import generate_evaluation_ai_advice
from app.services.backtest_lab.evaluation import run_target_evaluation
from app.services.backtest_lab.scoring import (
    calculate_evaluation_score,
    score_to_conclusion,
    summarize_result_group,
    summarize_trade_health,
)
from app.services.backtest_lab.target_selection import select_cross_asset_targets, select_time_ranges, strategy_country_code
from app.services.settings_service import get_performance_score_weights


EVALUATION_STATUS_LABELS = {
    "not_evaluated": "未评估",
    "evaluating": "评估中",
    "queued": "评估中",
    "running": "评估中",
    "success": "已完成",
    "failure": "失败",
}
EVALUATION_SOURCE_LABEL = "自动创建"


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


def backtest_lab_strategy_to_dict(strategy: Strategy, evaluation: StrategyEvaluation | None) -> dict:
    evaluation_payload = evaluation.to_dict() if evaluation else None
    status = evaluation.status if evaluation else "not_evaluated"
    return {
        "id": strategy.id,
        "name": strategy.name,
        "type": strategy.type,
        "source": EVALUATION_SOURCE_LABEL,
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
