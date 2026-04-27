from __future__ import annotations


def _format_curve_diagnostics_for_memory(diagnostics: dict) -> str:
    if not diagnostics:
        return "暂无"
    overview = diagnostics.get("overview") or {}
    relative = diagnostics.get("relativePerformance") or {}
    longest_cash = diagnostics.get("longestCashPeriod") or {}
    missed = diagnostics.get("missedUptrends") or []
    defensive = diagnostics.get("defensivePeriods") or []
    entry_quality = diagnostics.get("entryQuality") or {}
    exit_quality = diagnostics.get("exitQuality") or {}
    position_behavior = diagnostics.get("positionBehavior") or {}
    risk_behavior = diagnostics.get("riskBehavior") or {}
    diagnosis = diagnostics.get("diagnosis") or {}
    regimes = diagnostics.get("marketRegimes") or []
    parts = [
        f"总收益 策略 {overview.get('strategyReturn', '-')}% / 买入持有基准 {overview.get('benchmarkReturn', '-')}%",
        f"相对强弱 {relative.get('trend', '-')}（相对收益 {relative.get('relativeReturn', '-')}%，相对回撤 {relative.get('relativeMaxDrawdown', '-')}%）",
        f"持仓占比 {diagnostics.get('holdingRatio', 0)}%",
        f"跑赢买入持有基准天数占比 {diagnostics.get('outperformRatio', 0)}%",
    ]
    if longest_cash.get("tradingDays"):
        parts.append(
            f"最长空仓 {longest_cash.get('tradingDays')} 个交易日"
            f"（{longest_cash.get('startDate')} 至 {longest_cash.get('endDate')}）"
        )
    if missed:
        item = missed[0]
        parts.append(
            "最大错失上涨 "
            f"{item.get('startDate')} 至 {item.get('endDate')}："
            f"买入持有基准 {item.get('benchmarkReturn')}%，策略 {item.get('strategyReturn')}%，"
            f"差距 {item.get('gap')}%，持仓占比 {item.get('holdingRatio')}%，"
            f"均仓 {item.get('averagePosition')}%，原因：{item.get('reason')}"
        )
    if defensive:
        item = defensive[0]
        parts.append(
            "最有效避险 "
            f"{item.get('startDate')} 至 {item.get('endDate')}："
            f"买入持有基准 {item.get('benchmarkReturn')}%，策略 {item.get('strategyReturn')}%，"
            f"优势 {item.get('advantage')}%，持仓占比 {item.get('holdingRatio')}%，"
            f"原因：{item.get('reason')}"
        )
    if regimes:
        worst_regime = regimes[0]
        parts.append(
            f"关键行情段 {worst_regime.get('startDate')} 至 {worst_regime.get('endDate')}"
            f"（{worst_regime.get('regimeLabel')}）：策略 {worst_regime.get('strategyReturn')}%，"
            f"买入持有基准 {worst_regime.get('benchmarkReturn')}%，诊断：{worst_regime.get('diagnosis')}"
        )
    parts.append(
        f"入场质量：{entry_quality.get('diagnosis', '暂无')}，"
        f"买入后20日均值 {entry_quality.get('avg20dReturn', 0)}%，胜率 {entry_quality.get('winRate20d', 0)}%"
    )
    parts.append(
        f"出场质量：{exit_quality.get('diagnosis', '暂无')}，"
        f"卖出后20日均值 {exit_quality.get('avgPost20dReturn', 0)}%，"
        f"继续上涨比例 {exit_quality.get('continuedUpRatio20d', 0)}%"
    )
    parts.append(
        f"仓位行为：{position_behavior.get('diagnosis', '暂无')}，"
        f"平均仓位 {position_behavior.get('averagePosition', 0)}%，空仓占比 {position_behavior.get('cashRatio', 0)}%"
    )
    parts.append(f"风险行为：{risk_behavior.get('diagnosis', '暂无')}")
    if diagnosis.get("suggestion"):
        parts.append(f"建议：{diagnosis.get('suggestion')}")
    return "；".join(parts)



def _build_equity_curve_diagnostics(preview: dict) -> dict:
    equity_curve = preview.get("equityCurve") or []
    benchmark_curve = preview.get("benchmarkCurve") or []
    trades = preview.get("trades") or []
    total_days = min(len(equity_curve), len(benchmark_curve))
    if total_days <= 1:
        return {
            "overview": {},
            "relativePerformance": {},
            "marketRegimes": [],
            "holdingRatio": 0.0,
            "longestCashPeriod": None,
            "outperformRatio": 0.0,
            "missedUptrends": [],
            "defensivePeriods": [],
            "tradeAttribution": [],
            "entryQuality": {},
            "exitQuality": {},
            "positionBehavior": {},
            "riskBehavior": {},
            "diagnosis": {},
        }

    dates = [str(item.get("date")) for item in equity_curve[:total_days]]
    equity_values = [float(item.get("value") or 0) for item in equity_curve[:total_days]]
    benchmark_values = [float(item.get("value") or 0) for item in benchmark_curve[:total_days]]
    holding_flags = _build_holding_flags(dates, trades)
    position_ratios = _build_position_ratio_series(dates, trades)

    holding_days = sum(1 for flag in holding_flags if flag)
    outperform_days = sum(
        1
        for strategy_value, benchmark_value in zip(equity_values, benchmark_values, strict=False)
        if strategy_value >= benchmark_value * 0.999
    )
    missed_uptrends = _find_curve_windows(
        dates,
        equity_values,
        benchmark_values,
        holding_flags,
        position_ratios,
        trades,
        kind="missed_uptrend",
    )
    defensive_periods = _find_curve_windows(
        dates,
        equity_values,
        benchmark_values,
        holding_flags,
        position_ratios,
        trades,
        kind="defensive_period",
    )
    entry_quality = _build_entry_quality(dates, benchmark_values, trades)
    exit_quality = _build_exit_quality(dates, benchmark_values, trades)
    position_behavior = _build_position_behavior(dates, holding_flags, position_ratios, trades)
    risk_behavior = _build_risk_behavior(trades)

    diagnostics = {
        "overview": _build_curve_overview(dates, equity_values, benchmark_values),
        "relativePerformance": _build_relative_performance(dates, equity_values, benchmark_values),
        "marketRegimes": _build_market_regimes(dates, equity_values, benchmark_values, holding_flags, trades),
        "holdingRatio": round((holding_days / total_days) * 100, 2),
        "longestCashPeriod": _find_longest_cash_period(dates, holding_flags),
        "outperformRatio": round((outperform_days / total_days) * 100, 2),
        "missedUptrends": missed_uptrends,
        "defensivePeriods": defensive_periods,
        "tradeAttribution": _build_trade_attribution(dates, benchmark_values, trades),
        "entryQuality": entry_quality,
        "exitQuality": exit_quality,
        "positionBehavior": position_behavior,
        "riskBehavior": risk_behavior,
    }
    diagnostics["diagnosis"] = _build_curve_diagnosis(
        diagnostics,
        entry_quality,
        exit_quality,
        position_behavior,
        risk_behavior,
    )
    return diagnostics


def _build_holding_flags(dates: list[str], trades: list[dict]) -> list[bool]:
    trades_by_date: dict[str, list[dict]] = {}
    for trade in trades:
        trade_date = str(trade.get("date") or "")
        if trade_date:
            trades_by_date.setdefault(trade_date, []).append(trade)

    holding = False
    flags: list[bool] = []
    for current_date in dates:
        day_trades = trades_by_date.get(current_date, [])
        for trade in day_trades:
            if trade.get("side") == "buy":
                holding = True
            elif trade.get("side") == "sell":
                holding = False
        flags.append(holding)
    return flags


def _build_position_ratio_series(dates: list[str], trades: list[dict]) -> list[float]:
    trades_by_date: dict[str, list[dict]] = {}
    for trade in trades:
        trade_date = str(trade.get("date") or "")
        if trade_date:
            trades_by_date.setdefault(trade_date, []).append(trade)

    current_ratio = 0.0
    ratios: list[float] = []
    for current_date in dates:
        for trade in trades_by_date.get(current_date, []):
            if trade.get("side") == "buy":
                current_ratio = float(trade.get("positionRatio") or current_ratio or 0)
            elif trade.get("side") == "sell":
                current_ratio = 0.0
        ratios.append(round(current_ratio, 2))
    return ratios


def _find_longest_cash_period(dates: list[str], holding_flags: list[bool]) -> dict | None:
    best_start: int | None = None
    best_end: int | None = None
    current_start: int | None = None
    for index, is_holding in enumerate(holding_flags):
        if not is_holding:
            if current_start is None:
                current_start = index
            continue
        if current_start is not None:
            if best_start is None or index - current_start > best_end - best_start + 1:
                best_start = current_start
                best_end = index - 1
            current_start = None

    if current_start is not None:
        index = len(holding_flags)
        if best_start is None or index - current_start > best_end - best_start + 1:
            best_start = current_start
            best_end = index - 1

    if best_start is None or best_end is None:
        return None
    return {
        "startDate": dates[best_start],
        "endDate": dates[best_end],
        "tradingDays": best_end - best_start + 1,
    }


def _build_curve_overview(dates: list[str], equity_values: list[float], benchmark_values: list[float]) -> dict:
    return {
        "strategyReturn": round(_window_return(equity_values[0], equity_values[-1]), 2),
        "benchmarkReturn": round(_window_return(benchmark_values[0], benchmark_values[-1]), 2),
        "strategyNewHighCount": _count_new_highs(equity_values),
        "benchmarkNewHighCount": _count_new_highs(benchmark_values),
        "strategyMaxUnderwaterDays": _max_underwater_days(equity_values),
        "benchmarkMaxUnderwaterDays": _max_underwater_days(benchmark_values),
        "strategyLongestNoNewHighPeriod": _longest_no_new_high_period(dates, equity_values),
    }


def _build_relative_performance(dates: list[str], equity_values: list[float], benchmark_values: list[float]) -> dict:
    relative_values = [
        equity / benchmark if benchmark > 0 else 1.0
        for equity, benchmark in zip(equity_values, benchmark_values, strict=False)
    ]
    relative_return = _window_return(relative_values[0], relative_values[-1])
    trend = "上升" if relative_return >= 3 else "下降" if relative_return <= -3 else "横盘"
    outperform_flags = [value >= relative_values[0] * 0.999 for value in relative_values]
    underperform_flags = [not flag for flag in outperform_flags]
    return {
        "trend": trend,
        "relativeReturn": round(relative_return, 2),
        "relativeMaxDrawdown": round(_calculate_series_max_drawdown(relative_values) * 100, 2),
        "longestOutperformPeriod": _find_longest_flag_period(dates, outperform_flags),
        "longestUnderperformPeriod": _find_longest_flag_period(dates, underperform_flags),
        "relativeNewHighCount": _count_new_highs(relative_values),
    }


def _build_market_regimes(
    dates: list[str],
    equity_values: list[float],
    benchmark_values: list[float],
    holding_flags: list[bool],
    trades: list[dict],
) -> list[dict]:
    regimes: list[dict] = []
    window = 60
    step = 20
    if len(dates) <= window:
        return regimes
    for start in range(0, len(dates) - window, step):
        end = start + window
        benchmark_return = _window_return(benchmark_values[start], benchmark_values[end])
        strategy_return = _window_return(equity_values[start], equity_values[end])
        regime = "uptrend" if benchmark_return > 8 else "downtrend" if benchmark_return < -8 else "sideways"
        holding_ratio = _ratio(sum(1 for flag in holding_flags[start : end + 1] if flag), window + 1)
        trade_count = _count_trades_between(trades, dates[start], dates[end])
        regimes.append(
            {
                "startDate": dates[start],
                "endDate": dates[end],
                "regime": regime,
                "regimeLabel": {"uptrend": "上涨趋势", "downtrend": "下跌趋势", "sideways": "震荡"}.get(regime, regime),
                "benchmarkReturn": round(benchmark_return, 2),
                "strategyReturn": round(strategy_return, 2),
                "holdingRatio": holding_ratio,
                "tradeCount": trade_count,
                "diagnosis": _diagnose_regime(regime, benchmark_return, strategy_return, holding_ratio),
            }
        )
    return sorted(
        regimes,
        key=lambda item: abs(float(item.get("benchmarkReturn") or 0) - float(item.get("strategyReturn") or 0)),
        reverse=True,
    )[:6]


def _find_curve_windows(
    dates: list[str],
    equity_values: list[float],
    benchmark_values: list[float],
    holding_flags: list[bool],
    position_ratios: list[float],
    trades: list[dict],
    *,
    kind: str,
) -> list[dict]:
    candidates: list[dict] = []
    for window in (20, 60, 120):
        if len(dates) <= window:
            continue
        for start in range(0, len(dates) - window):
            end = start + window
            strategy_return = _window_return(equity_values[start], equity_values[end])
            benchmark_return = _window_return(benchmark_values[start], benchmark_values[end])
            holding_ratio = round((sum(1 for flag in holding_flags[start : end + 1] if flag) / (window + 1)) * 100, 2)
            average_position = round(_average(position_ratios[start : end + 1]), 2)
            buy_count = _count_trades_between(trades, dates[start], dates[end], side="buy")
            sell_count = _count_trades_between(trades, dates[start], dates[end], side="sell")
            if kind == "missed_uptrend":
                gap = benchmark_return - strategy_return
                if benchmark_return >= 8 and gap >= 5:
                    candidates.append(
                        {
                            "startIndex": start,
                            "endIndex": end,
                            "startDate": dates[start],
                            "endDate": dates[end],
                            "benchmarkReturn": round(benchmark_return, 2),
                            "strategyReturn": round(strategy_return, 2),
                            "gap": round(gap, 2),
                            "holdingRatio": holding_ratio,
                            "averagePosition": average_position,
                            "buyCount": buy_count,
                            "sellCount": sell_count,
                            "reason": _infer_missed_uptrend_reason(holding_ratio, average_position, buy_count, sell_count),
                            "score": gap * max(benchmark_return, 0),
                        }
                    )
            else:
                advantage = strategy_return - benchmark_return
                if benchmark_return <= -8 and advantage >= 5:
                    candidates.append(
                        {
                            "startIndex": start,
                            "endIndex": end,
                            "startDate": dates[start],
                            "endDate": dates[end],
                            "benchmarkReturn": round(benchmark_return, 2),
                            "strategyReturn": round(strategy_return, 2),
                            "advantage": round(advantage, 2),
                            "holdingRatio": holding_ratio,
                            "averagePosition": average_position,
                            "buyCount": buy_count,
                            "sellCount": sell_count,
                            "reason": _infer_defensive_reason(holding_ratio, sell_count),
                            "score": advantage * abs(benchmark_return),
                        }
                    )

    merged = _merge_curve_windows(candidates, kind=kind)
    return [
        {key: value for key, value in item.items() if key not in {"startIndex", "endIndex", "score"}}
        for item in sorted(merged, key=lambda item: item.get("score", 0), reverse=True)[:3]
    ]


def _merge_curve_windows(candidates: list[dict], *, kind: str) -> list[dict]:
    if not candidates:
        return []
    ordered = sorted(candidates, key=lambda item: (item["startIndex"], item["endIndex"]))
    merged: list[dict] = []
    for item in ordered:
        if not merged or item["startIndex"] > merged[-1]["endIndex"] + 5:
            merged.append(item.copy())
            continue
        current = merged[-1]
        if item.get("score", 0) > current.get("score", 0):
            current.update(item)
        else:
            current["endIndex"] = max(current["endIndex"], item["endIndex"])
            current["endDate"] = item["endDate"] if item["endIndex"] >= current["endIndex"] else current["endDate"]
        metric_key = "gap" if kind == "missed_uptrend" else "advantage"
        if item.get(metric_key, 0) > current.get(metric_key, 0):
            current[metric_key] = item[metric_key]
            current["benchmarkReturn"] = item["benchmarkReturn"]
            current["strategyReturn"] = item["strategyReturn"]
            current["holdingRatio"] = item["holdingRatio"]
            current["score"] = item["score"]
    return merged


def _window_return(start_value: float, end_value: float) -> float:
    if start_value <= 0:
        return 0.0
    return ((end_value / start_value) - 1) * 100


def _average(values: list[float] | list[int]) -> float:
    cleaned = [float(value) for value in values if value is not None]
    return sum(cleaned) / len(cleaned) if cleaned else 0.0


def _ratio(numerator: int | float, denominator: int | float) -> float:
    return round((float(numerator) / float(denominator)) * 100, 2) if denominator else 0.0


def _future_return(values: list[float], index: int, days: int) -> float:
    if index < 0 or index >= len(values):
        return 0.0
    end = min(index + days, len(values) - 1)
    return round(_window_return(values[index], values[end]), 2)


def _future_max_return(values: list[float], index: int, days: int) -> float:
    if index < 0 or index >= len(values):
        return 0.0
    end = min(index + days, len(values) - 1)
    start_value = values[index]
    if start_value <= 0:
        return 0.0
    return round(max(_window_return(start_value, value) for value in values[index : end + 1]), 2)


def _future_min_return(values: list[float], index: int, days: int) -> float:
    if index < 0 or index >= len(values):
        return 0.0
    end = min(index + days, len(values) - 1)
    start_value = values[index]
    if start_value <= 0:
        return 0.0
    return round(min(_window_return(start_value, value) for value in values[index : end + 1]), 2)


def _count_new_highs(values: list[float]) -> int:
    high = float("-inf")
    count = 0
    for value in values:
        if value > high:
            high = value
            count += 1
    return count


def _max_underwater_days(values: list[float]) -> int:
    high = float("-inf")
    current = 0
    best = 0
    for value in values:
        if value >= high:
            high = value
            current = 0
        else:
            current += 1
            best = max(best, current)
    return best


def _longest_no_new_high_period(dates: list[str], values: list[float]) -> dict | None:
    high = float("-inf")
    current_start: int | None = None
    best: tuple[int, int] | None = None
    for index, value in enumerate(values):
        if value >= high:
            if current_start is not None and index - current_start > 0:
                candidate = (current_start, index - 1)
                if best is None or candidate[1] - candidate[0] > best[1] - best[0]:
                    best = candidate
            high = value
            current_start = index + 1
    if current_start is not None and current_start < len(values):
        candidate = (current_start, len(values) - 1)
        if best is None or candidate[1] - candidate[0] > best[1] - best[0]:
            best = candidate
    if not best:
        return None
    return {"startDate": dates[best[0]], "endDate": dates[best[1]], "tradingDays": best[1] - best[0] + 1}


def _calculate_series_max_drawdown(values: list[float]) -> float:
    high = values[0] if values else 0.0
    max_drawdown = 0.0
    for value in values:
        high = max(high, value)
        if high > 0:
            max_drawdown = max(max_drawdown, (high - value) / high)
    return max_drawdown


def _find_longest_flag_period(dates: list[str], flags: list[bool]) -> dict | None:
    best_start: int | None = None
    best_end: int | None = None
    current_start: int | None = None
    for index, flag in enumerate(flags):
        if flag:
            if current_start is None:
                current_start = index
            continue
        if current_start is not None:
            if best_start is None or index - current_start > best_end - best_start + 1:
                best_start = current_start
                best_end = index - 1
            current_start = None
    if current_start is not None:
        index = len(flags)
        if best_start is None or index - current_start > best_end - best_start + 1:
            best_start = current_start
            best_end = index - 1
    if best_start is None or best_end is None:
        return None
    return {"startDate": dates[best_start], "endDate": dates[best_end], "tradingDays": best_end - best_start + 1}


def _count_trades_between(trades: list[dict], start_date: str, end_date: str, side: str | None = None) -> int:
    return sum(
        1
        for trade in trades
        if start_date <= str(trade.get("date") or "") <= end_date
        and (side is None or trade.get("side") == side)
    )


def _infer_missed_uptrend_reason(holding_ratio: float, average_position: float, buy_count: int, sell_count: int) -> str:
    if holding_ratio <= 10:
        return "完全或长期空仓，买入条件过严"
    if buy_count == 0:
        return "没有触发买入，入场条件错过上涨"
    if average_position < 35:
        return "仓位不足或加仓太慢，上涨参与度不够"
    if sell_count > buy_count:
        return "中途卖出偏早，趋势持有不足"
    return "上涨阶段参与不足"


def _infer_defensive_reason(holding_ratio: float, sell_count: int) -> str:
    if holding_ratio <= 20 and sell_count > 0:
        return "提前离场，防守有效"
    if holding_ratio <= 20:
        return "低仓位或空仓规避下跌"
    return "持仓下跌更少，风险控制有效"


def _diagnose_regime(regime: str, benchmark_return: float, strategy_return: float, holding_ratio: float) -> str:
    if regime == "uptrend" and strategy_return < benchmark_return * 0.5:
        return "上涨阶段参与不足" if holding_ratio < 50 else "持仓但收益弹性不足"
    if regime == "downtrend" and strategy_return > benchmark_return + 5:
        return "下跌阶段防守有效"
    if regime == "sideways" and strategy_return > benchmark_return + 3:
        return "震荡阶段交易有效"
    if regime == "sideways" and strategy_return < benchmark_return - 3:
        return "震荡阶段被反复消耗"
    return "表现接近市场阶段特征"


def _pair_round_trips(trades: list[dict]) -> list[dict]:
    open_buys: list[dict] = []
    results: list[dict] = []
    for trade in trades:
        side = trade.get("side")
        if side == "buy":
            open_buys.append(trade)
            continue
        if side != "sell" or not open_buys:
            continue
        results.append(
            {
                "entryDate": str(open_buys[0].get("date") or ""),
                "exitDate": str(trade.get("date") or ""),
                "return": float(trade.get("return") or 0),
                "entryPositionRatio": float(open_buys[-1].get("positionRatio") or 0),
                "exitReason": str(trade.get("reason") or ""),
            }
        )
        open_buys = []
    return results


def _classify_entry(return_20d: float) -> str:
    if return_20d >= 5:
        return "入场有效"
    if return_20d <= -5:
        return "入场偏差或追高"
    return "入场优势不明显"


def _classify_exit(post_exit_20d: float, reason: str) -> str:
    if post_exit_20d >= 5:
        return "卖出偏早或卖飞"
    if post_exit_20d <= -5:
        return "卖出后规避下跌"
    if "止损" in reason:
        return "止损后走势平稳，需继续观察"
    return "出场影响中性"


def _diagnose_entry_quality(returns_20d: list[float], adverse_20d: list[float]) -> str:
    if not returns_20d:
        return "没有买入样本"
    avg_return = _average(returns_20d)
    quick_drawdown_ratio = _ratio(sum(1 for value in adverse_20d if value <= -5), len(adverse_20d))
    if avg_return >= 3 and quick_drawdown_ratio <= 30:
        return "入场整体有效"
    if avg_return >= 0:
        return "入场略有效但优势不强"
    if quick_drawdown_ratio >= 50:
        return "入场后经常快速回撤，可能追高或确认不足"
    return "入场信号偏弱"


def _diagnose_exit_quality(post_returns_20d: list[float], max_down_after_exit: list[float]) -> str:
    if not post_returns_20d:
        return "没有卖出样本"
    avg_post = _average(post_returns_20d)
    avoid_down_ratio = _ratio(sum(1 for value in max_down_after_exit if value < -3), len(max_down_after_exit))
    if avg_post >= 4:
        return "卖出后仍明显上涨，出场偏早"
    if avg_post <= -4 or avoid_down_ratio >= 50:
        return "卖出有效，规避了后续下跌"
    return "出场整体中性"


def _diagnose_position_behavior(position_ratios: list[float], holding_flags: list[bool]) -> str:
    if not position_ratios:
        return "暂无仓位数据"
    avg_position = _average(position_ratios)
    cash_ratio = _ratio(sum(1 for flag in holding_flags if not flag), len(holding_flags))
    full_ratio = _ratio(sum(1 for value in position_ratios if value >= 95), len(position_ratios))
    if cash_ratio >= 60:
        return "长期空仓，可能错过趋势"
    if avg_position < 35:
        return "平均仓位偏低，上涨参与度可能不足"
    if full_ratio >= 70:
        return "长期高仓位，接近买入持有基准"
    return "仓位节奏相对均衡"


def _diagnose_risk_behavior(reason_counts: dict, losing_sells: list[float]) -> str:
    if not reason_counts:
        return "暂无风控样本"
    if losing_sells and _average(losing_sells) <= -8:
        return "亏损卖出幅度偏大，出场可能滞后"
    return "风控触发分布正常"


def _build_curve_suggestion(diagnostics: dict, entry_quality: dict, exit_quality: dict, position_behavior: dict) -> str:
    missed = diagnostics.get("missedUptrends") or []
    defensive = diagnostics.get("defensivePeriods") or []
    suggestions: list[str] = []
    if missed:
        suggestions.append("优先修复上涨阶段参与不足，放宽有效趋势下的入场或加仓条件")
    if defensive:
        suggestions.append("保留已有防守规则，避免为了追收益完全破坏避险能力")
    if "卖出偏早" in str(exit_quality.get("diagnosis")):
        suggestions.append("检查卖出规则，减少过早离场或提高趋势持有容忍度")
    if "长期空仓" in str(position_behavior.get("diagnosis")) or "平均仓位偏低" in str(position_behavior.get("diagnosis")):
        suggestions.append("提高趋势确认后的持仓时间或仓位利用率")
    if not suggestions:
        suggestions.append("从入场质量、出场质量和跨时间验证中选择一个主要矛盾做小步调整")
    return "；".join(suggestions)


def _build_trade_attribution(dates: list[str], benchmark_values: list[float], trades: list[dict]) -> list[dict]:
    date_index = {date_text: index for index, date_text in enumerate(dates)}
    round_trips = _pair_round_trips(trades)
    results: list[dict] = []
    for trade in round_trips[:20]:
        entry_index = date_index.get(trade["entryDate"])
        exit_index = date_index.get(trade["exitDate"])
        if entry_index is None or exit_index is None:
            continue
        post_exit_20d = _future_return(benchmark_values, exit_index, 20)
        entry_20d = _future_return(benchmark_values, entry_index, 20)
        results.append(
            {
                "entryDate": trade["entryDate"],
                "exitDate": trade["exitDate"],
                "holdingDays": max(exit_index - entry_index, 0),
                "return": trade["return"],
                "entryPositionRatio": trade["entryPositionRatio"],
                "exitReason": trade["exitReason"],
                "entry20dBenchmarkReturn": entry_20d,
                "postExit20dBenchmarkReturn": post_exit_20d,
                "entryDiagnosis": _classify_entry(entry_20d),
                "exitDiagnosis": _classify_exit(post_exit_20d, trade["exitReason"]),
            }
        )
    return sorted(results, key=lambda item: abs(float(item.get("return") or 0)), reverse=True)[:8]


def _build_entry_quality(dates: list[str], benchmark_values: list[float], trades: list[dict]) -> dict:
    date_index = {date_text: index for index, date_text in enumerate(dates)}
    returns_5d: list[float] = []
    returns_20d: list[float] = []
    max_adverse_20d: list[float] = []
    for trade in trades:
        if trade.get("side") != "buy":
            continue
        index = date_index.get(str(trade.get("date") or ""))
        if index is None:
            continue
        returns_5d.append(_future_return(benchmark_values, index, 5))
        returns_20d.append(_future_return(benchmark_values, index, 20))
        max_adverse_20d.append(_future_min_return(benchmark_values, index, 20))
    return {
        "buyCount": len(returns_20d),
        "avg5dReturn": round(_average(returns_5d), 2),
        "avg20dReturn": round(_average(returns_20d), 2),
        "winRate20d": _ratio(sum(1 for value in returns_20d if value > 0), len(returns_20d)),
        "avgMaxAdverse20d": round(_average(max_adverse_20d), 2),
        "quickDrawdownRatio": _ratio(sum(1 for value in max_adverse_20d if value <= -5), len(max_adverse_20d)),
        "diagnosis": _diagnose_entry_quality(returns_20d, max_adverse_20d),
    }


def _build_exit_quality(dates: list[str], benchmark_values: list[float], trades: list[dict]) -> dict:
    date_index = {date_text: index for index, date_text in enumerate(dates)}
    post_returns_5d: list[float] = []
    post_returns_20d: list[float] = []
    max_up_after_exit: list[float] = []
    max_down_after_exit: list[float] = []
    for trade in trades:
        if trade.get("side") != "sell":
            continue
        index = date_index.get(str(trade.get("date") or ""))
        if index is None:
            continue
        post_returns_5d.append(_future_return(benchmark_values, index, 5))
        post_returns_20d.append(_future_return(benchmark_values, index, 20))
        max_up_after_exit.append(_future_max_return(benchmark_values, index, 20))
        max_down_after_exit.append(_future_min_return(benchmark_values, index, 20))
    return {
        "sellCount": len(post_returns_20d),
        "avgPost5dReturn": round(_average(post_returns_5d), 2),
        "avgPost20dReturn": round(_average(post_returns_20d), 2),
        "continuedUpRatio20d": _ratio(sum(1 for value in post_returns_20d if value > 3), len(post_returns_20d)),
        "avoidDownRatio20d": _ratio(sum(1 for value in max_down_after_exit if value < -3), len(max_down_after_exit)),
        "avgMaxUpAfterExit20d": round(_average(max_up_after_exit), 2),
        "avgMaxDownAfterExit20d": round(_average(max_down_after_exit), 2),
        "diagnosis": _diagnose_exit_quality(post_returns_20d, max_down_after_exit),
    }


def _build_position_behavior(
    dates: list[str],
    holding_flags: list[bool],
    position_ratios: list[float],
    trades: list[dict],
) -> dict:
    buy_dates = [str(trade.get("date") or "") for trade in trades if trade.get("side") == "buy"]
    buy_indexes = [dates.index(item) for item in buy_dates if item in dates]
    intervals = [
        buy_indexes[index] - buy_indexes[index - 1]
        for index in range(1, len(buy_indexes))
    ]
    return {
        "averagePosition": round(_average(position_ratios), 2),
        "maxPosition": round(max(position_ratios) if position_ratios else 0, 2),
        "fullPositionRatio": _ratio(sum(1 for value in position_ratios if value >= 95), len(position_ratios)),
        "cashRatio": _ratio(sum(1 for flag in holding_flags if not flag), len(holding_flags)),
        "addCount": max(len(buy_indexes) - sum(1 for trade in trades if trade.get("side") == "sell"), 0),
        "avgAddInterval": round(_average(intervals), 2),
        "diagnosis": _diagnose_position_behavior(position_ratios, holding_flags),
    }


def _build_risk_behavior(trades: list[dict]) -> dict:
    sell_reasons = [str(trade.get("reason") or "") for trade in trades if trade.get("side") == "sell"]
    reason_counts = {
        "exitRule": sum(1 for reason in sell_reasons if "卖出规则" in reason),
        "forceClose": sum(1 for reason in sell_reasons if "强制平仓" in reason),
    }
    losing_sells = [
        float(trade.get("return") or 0)
        for trade in trades
        if trade.get("side") == "sell" and float(trade.get("return") or 0) < 0
    ]
    return {
        "sellReasonCounts": reason_counts,
        "lossSellCount": len(losing_sells),
        "avgLosingSellReturn": round(_average(losing_sells), 2),
        "diagnosis": _diagnose_risk_behavior(reason_counts, losing_sells),
    }


def _build_curve_diagnosis(
    diagnostics: dict,
    entry_quality: dict,
    exit_quality: dict,
    position_behavior: dict,
    risk_behavior: dict,
) -> dict:
    items = []
    missed = diagnostics.get("missedUptrends") or []
    defensive = diagnostics.get("defensivePeriods") or []
    if missed:
        items.append(f"最大问题：{missed[0].get('reason')}，发生在 {missed[0].get('startDate')} 至 {missed[0].get('endDate')}。")
    if defensive:
        items.append(f"主要优势：{defensive[0].get('reason')}，发生在 {defensive[0].get('startDate')} 至 {defensive[0].get('endDate')}。")
    items.extend(
        [
            f"入场质量：{entry_quality.get('diagnosis', '暂无')}",
            f"出场质量：{exit_quality.get('diagnosis', '暂无')}",
            f"仓位行为：{position_behavior.get('diagnosis', '暂无')}",
            f"风险行为：{risk_behavior.get('diagnosis', '暂无')}",
        ]
    )
    return {
        "summary": items,
        "suggestion": _build_curve_suggestion(diagnostics, entry_quality, exit_quality, position_behavior),
    }


