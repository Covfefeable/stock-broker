from __future__ import annotations

from copy import deepcopy

from app.models.strategy import Strategy
from app.services.backtest_lab.scoring import calculate_sample_score, result_passes
from app.services.performance_score import calculate_performance_score
from app.services.strategies import _load_asset_bars, _run_strategy_backtest


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


def build_result_reason(preview: dict, passed: bool, strategy_score: float, benchmark_score: float, sample_score: float) -> str:
    prefix = "通过" if passed else "未通过"
    return (
        f"{prefix}：样本分 {sample_score:.2f}，策略综合分 {strategy_score:.2f}，买入持有基准 {benchmark_score:.2f}；"
        f"年化 {preview.get('annualReturn')}%，买入持有基准 {preview.get('benchmarkAnnualReturn')}%，"
        f"回撤 {preview.get('maxDrawdown')}%，Sharpe {preview.get('sharpe')}，交易 {preview.get('tradeCount')} 次。"
    )
