from __future__ import annotations

from math import isnan, sqrt
from typing import Any


def calculate_sample_score(strategy_score: float, benchmark_score: float) -> float:
    return round(min(max(50.0 + (strategy_score - benchmark_score) * 2.0, 0.0), 100.0), 2)


def result_passes(sample_score: float) -> bool:
    return sample_score >= 52.0


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
