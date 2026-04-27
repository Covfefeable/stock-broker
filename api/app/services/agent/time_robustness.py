from __future__ import annotations

from datetime import date

from app.models.agent_task import AgentTask
from app.services.agent.curve_diagnostics import _build_equity_curve_diagnostics
from app.services.scoring import calculate_performance_score
from app.services.strategies import _load_asset_bars, _run_strategy_backtest


def _format_time_robustness_for_memory(time_robustness: dict) -> str:
    summary = time_robustness.get("summary") or {}
    if not summary:
        return "暂无"
    return (
        f"样本 {summary.get('sampleCount', 0)} 个，"
        f"跑赢买入持有基准 {summary.get('beatBenchmarkCount', 0)} 个，"
        f"通过率 {summary.get('passRate', 0)}%，"
        f"平均分差 {summary.get('averageScoreDiff', 0)}，"
        f"最差区间 {summary.get('worstRange') or '-'}，"
        f"原因 {summary.get('worstReason') or '-'}"
    )



TIME_ROBUSTNESS_RANGES = (
    ("recent_1y", "近一年", 1),
    ("recent_3y", "近三年", 3),
    ("recent_5y", "近五年", 5),
)


def _resolve_preview_range(task: AgentTask, range_key: str | None) -> dict:
    normalized_key = str(range_key or "current").strip()
    end_date = task.backtest_end_date or date.today()
    if normalized_key in {"", "current"}:
        start_date = task.backtest_start_date
        if not start_date:
            raise ValueError("Agent 任务缺少回测开始日期。")
        return {
            "key": "current",
            "label": "当前回测区间",
            "startDate": start_date,
            "endDate": end_date,
        }

    for key, label, years in TIME_ROBUSTNESS_RANGES:
        if normalized_key == key:
            return {
                "key": key,
                "label": label,
                "startDate": _shift_year(end_date, -years),
                "endDate": end_date,
            }
    raise ValueError("不支持的收益预览区间。")


def _shift_year(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(year=value.year + years, day=28)


def _build_time_robustness_summary(
    task: AgentTask,
    strategy_config: dict,
    *,
    score_weights: dict[str, float] | None = None,
) -> dict:
    samples: list[dict] = []
    for key, label, _years in TIME_ROBUSTNESS_RANGES:
        range_config = _resolve_preview_range(task, key)
        try:
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
            if len([bar for bar in bars if not bar.get("isWarmup")]) < 60:
                samples.append(
                    {
                        "key": key,
                        "label": label,
                        "status": "skipped",
                        "reason": "可用 K 线少于 60 条。",
                    }
                )
                continue
            preview = _run_strategy_backtest(bars, strategy_config)
            strategy_score = calculate_performance_score(preview.get("annualReturn"), preview.get("sharpe"), preview.get("maxDrawdown"), weights=score_weights)
            benchmark_score = calculate_performance_score(
                preview.get("benchmarkAnnualReturn"),
                preview.get("benchmarkSharpe"),
                preview.get("benchmarkMaxDrawdown"),
                weights=score_weights,
            )
            samples.append(
                {
                    "key": key,
                    "label": label,
                    "status": "success",
                    "dateRange": preview.get("dateRange"),
                    "score": round(strategy_score, 2),
                    "benchmarkScore": round(benchmark_score, 2),
                    "scoreDiff": round(strategy_score - benchmark_score, 2),
                    "annualReturn": round(float(preview.get("annualReturn") or 0), 2),
                    "benchmarkAnnualReturn": round(float(preview.get("benchmarkAnnualReturn") or 0), 2),
                    "maxDrawdown": round(float(preview.get("maxDrawdown") or 0), 2),
                    "benchmarkMaxDrawdown": round(float(preview.get("benchmarkMaxDrawdown") or 0), 2),
                    "sharpe": round(float(preview.get("sharpe") or 0), 2),
                    "benchmarkSharpe": round(float(preview.get("benchmarkSharpe") or 0), 2),
                    "tradeCount": preview.get("tradeCount"),
                    "benchmarkTradeCount": preview.get("benchmarkTradeCount"),
                    "diagnostics": _build_equity_curve_diagnostics(preview),
                    "diagnosis": _build_time_sample_diagnosis(preview, strategy_score, benchmark_score),
                }
            )
        except Exception as exc:  # noqa: BLE001
            samples.append(
                {
                    "key": key,
                    "label": label,
                    "status": "failed",
                    "reason": str(exc),
                }
            )

    success_samples = [item for item in samples if item.get("status") == "success"]
    diffs = [float(item.get("scoreDiff") or 0) for item in success_samples]
    scores = [float(item.get("score") or 0) for item in success_samples]
    beat_count = sum(1 for diff in diffs if diff >= 0)
    worst = min(success_samples, key=lambda item: float(item.get("scoreDiff") or 0), default=None)
    return {
        "summary": {
            "sampleCount": len(success_samples),
            "beatBenchmarkCount": beat_count,
            "passRate": round((beat_count / len(success_samples)) * 100, 2) if success_samples else 0.0,
            "averageScore": round(sum(scores) / len(scores), 2) if scores else 0.0,
            "averageScoreDiff": round(sum(diffs) / len(diffs), 2) if diffs else 0.0,
            "worstRange": worst.get("label") if worst else None,
            "worstScoreDiff": worst.get("scoreDiff") if worst else None,
            "worstReason": worst.get("diagnosis") if worst else None,
        },
        "samples": samples,
    }


def _build_time_sample_diagnosis(preview: dict, strategy_score: float, benchmark_score: float) -> str:
    problems: list[str] = []
    if strategy_score < benchmark_score:
        problems.append("综合分弱于买入持有基准")
    if float(preview.get("annualReturn") or 0) < float(preview.get("benchmarkAnnualReturn") or 0):
        problems.append("收益不足")
    if float(preview.get("maxDrawdown") or 0) > float(preview.get("benchmarkMaxDrawdown") or 0):
        problems.append("回撤更高")
    trade_count = int(preview.get("tradeCount") or 0)
    if trade_count < 2:
        problems.append("交易次数过低")
    elif trade_count > 120:
        problems.append("交易次数过高")
    return "、".join(problems) if problems else "表现优于或接近买入持有基准"
