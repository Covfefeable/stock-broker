from __future__ import annotations

from math import sqrt


def _calculate_indicators(bars: list[dict]) -> dict[str, list[float | None]]:
    closes = [bar["close"] for bar in bars]
    highs = [bar["high"] for bar in bars]
    lows = [bar["low"] for bar in bars]

    opens = [bar["open"] for bar in bars]
    volumes = [bar["volume"] for bar in bars]

    ma5 = _simple_moving_average(closes, 5)
    ma10 = _simple_moving_average(closes, 10)
    ma20 = _simple_moving_average(closes, 20)
    ma60 = _simple_moving_average(closes, 60)
    ma120 = _simple_moving_average(closes, 120)
    rsi14 = _rsi_wilder(closes, 14)
    macd_dif, macd_dea = _macd(closes)
    kdj_k, kdj_d = _kdj(highs, lows, closes)
    bias_ma20 = _ratio_to_series(closes, ma20)
    atr14 = _atr(highs, lows, closes, 14)
    atr14_pct = _series_ratio(atr14, closes)
    volatility_20d = _rolling_volatility(closes, 20)
    range_pct = _range_pct(highs, lows, closes)
    gap_pct = _gap_pct(opens, closes)
    high20 = _rolling_max(highs, 20)
    low20 = _rolling_min(lows, 20)
    high60 = _rolling_max(highs, 60)
    low60 = _rolling_min(lows, 60)
    close_pct_of_20d_range = _range_position(closes, low20, high20)
    close_pct_of_60d_range = _range_position(closes, low60, high60)
    distance_to_20d_high = _distance_to_series(closes, high20)
    distance_to_20d_low = _distance_to_series(closes, low20)

    return {
        "ma5": ma5,
        "ma10": ma10,
        "ma20": ma20,
        "ma60": ma60,
        "ma120": ma120,
        "rsi14": rsi14,
        "macd_dif": macd_dif,
        "macd_dea": macd_dea,
        "kdj_k": kdj_k,
        "kdj_d": kdj_d,
        "bias_ma20": bias_ma20,
        "atr14_pct": atr14_pct,
        "volatility_20d": volatility_20d,
        "range_pct": range_pct,
        "gap_pct": gap_pct,
        "close_pct_of_20d_range": close_pct_of_20d_range,
        "close_pct_of_60d_range": close_pct_of_60d_range,
        "distance_to_20d_high": distance_to_20d_high,
        "distance_to_20d_low": distance_to_20d_low,
    }


def _rolling_max(values: list[float | None], window: int) -> list[float | None]:
    result: list[float | None] = []
    for index in range(len(values)):
        window_values = [value for value in values[max(0, index - window + 1) : index + 1] if value is not None]
        result.append(round(max(window_values), 6) if len(window_values) == window else None)
    return result


def _rolling_min(values: list[float | None], window: int) -> list[float | None]:
    result: list[float | None] = []
    for index in range(len(values)):
        window_values = [value for value in values[max(0, index - window + 1) : index + 1] if value is not None]
        result.append(round(min(window_values), 6) if len(window_values) == window else None)
    return result


def _rate_of_change(values: list[float | None], periods: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    for index in range(periods, len(values)):
        current = values[index]
        previous = values[index - periods]
        if current is None or previous in (None, 0):
            continue
        result[index] = round((current / previous) - 1, 6)
    return result


def _ratio_to_series(values: list[float | None], denominator_series: list[float | None]) -> list[float | None]:
    result: list[float | None] = []
    for value, denominator in zip(values, denominator_series, strict=False):
        if value is None or denominator in (None, 0):
            result.append(None)
        else:
            result.append(round((value / denominator) - 1, 6))
    return result


def _series_ratio(values: list[float | None], denominator_series: list[float | None]) -> list[float | None]:
    result: list[float | None] = []
    for value, denominator in zip(values, denominator_series, strict=False):
        if value is None or denominator in (None, 0):
            result.append(None)
        else:
            result.append(round(value / denominator, 6))
    return result


def _distance_to_series(values: list[float | None], base_series: list[float | None]) -> list[float | None]:
    result: list[float | None] = []
    for value, base in zip(values, base_series, strict=False):
        if value is None or base in (None, 0):
            result.append(None)
        else:
            result.append(round((value / base) - 1, 6))
    return result


def _range_position(
    values: list[float | None],
    lows: list[float | None],
    highs: list[float | None],
) -> list[float | None]:
    result: list[float | None] = []
    for value, low, high in zip(values, lows, highs, strict=False):
        if value is None or low is None or high is None:
            result.append(None)
        elif high == low:
            result.append(0.5)
        else:
            result.append(round((value - low) / (high - low), 6))
    return result


def _true_range(high: float, low: float, previous_close: float | None) -> float:
    if previous_close is None:
        return high - low
    return max(high - low, abs(high - previous_close), abs(low - previous_close))


def _atr(highs: list[float | None], lows: list[float | None], closes: list[float | None], period: int) -> list[float | None]:
    true_ranges: list[float | None] = []
    previous_close: float | None = None
    for high, low, close in zip(highs, lows, closes, strict=False):
        if high is None or low is None:
            true_ranges.append(None)
        else:
            true_ranges.append(_true_range(high, low, previous_close))
        if close is not None:
            previous_close = close
    return _simple_moving_average(true_ranges, period)


def _rolling_volatility(closes: list[float | None], window: int) -> list[float | None]:
    daily_returns = _rate_of_change(closes, 1)
    result: list[float | None] = [None] * len(closes)
    for index in range(window, len(closes)):
        window_returns = [value for value in daily_returns[index - window + 1 : index + 1] if value is not None]
        if len(window_returns) != window:
            continue
        mean = sum(window_returns) / window
        variance = sum((item - mean) ** 2 for item in window_returns) / max(window - 1, 1)
        result[index] = round(sqrt(variance), 6)
    return result


def _range_pct(highs: list[float | None], lows: list[float | None], closes: list[float | None]) -> list[float | None]:
    result: list[float | None] = []
    for high_price, low_price, close_price in zip(highs, lows, closes, strict=False):
        if high_price is None or low_price is None or close_price in (None, 0):
            result.append(None)
        else:
            result.append(round((high_price - low_price) / close_price, 6))
    return result


def _gap_pct(opens: list[float | None], closes: list[float | None]) -> list[float | None]:
    result: list[float | None] = [None]
    for index in range(1, len(opens)):
        open_price = opens[index]
        previous_close = closes[index - 1]
        if open_price is None or previous_close in (None, 0):
            result.append(None)
            continue
        result.append(round((open_price / previous_close) - 1, 6))
    return result


def _simple_moving_average(values: list[float | None], window: int) -> list[float | None]:
    result: list[float | None] = []
    for index in range(len(values)):
        window_values = [value for value in values[max(0, index - window + 1) : index + 1] if value is not None]
        result.append(round(sum(window_values) / window, 6) if len(window_values) == window else None)
    return result


def _ema(values: list[float | None], period: int) -> list[float | None]:
    result: list[float | None] = []
    multiplier = 2 / (period + 1)
    ema_value: float | None = None
    for value in values:
        if value is None:
            result.append(ema_value)
            continue
        ema_value = value if ema_value is None else (value - ema_value) * multiplier + ema_value
        result.append(round(ema_value, 6))
    return result


def _macd(values: list[float | None]) -> tuple[list[float | None], list[float | None]]:
    ema12 = _ema(values, 12)
    ema26 = _ema(values, 26)
    dif = [
        round(fast - slow, 6) if fast is not None and slow is not None else None
        for fast, slow in zip(ema12, ema26, strict=False)
    ]
    dea = _ema(dif, 9)
    return dif, dea


def _rsi_wilder(values: list[float | None], period: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return result

    deltas: list[float] = []
    for index in range(1, len(values)):
        current = values[index]
        previous = values[index - 1]
        if current is None or previous is None:
            deltas.append(0.0)
        else:
            deltas.append(current - previous)

    gains = [max(delta, 0.0) for delta in deltas]
    losses = [abs(min(delta, 0.0)) for delta in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    result[period] = 100.0 if avg_loss == 0 else round(100 - (100 / (1 + avg_gain / avg_loss)), 6)

    for index in range(period + 1, len(values)):
        gain = gains[index - 1]
        loss = losses[index - 1]
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period
        result[index] = 100.0 if avg_loss == 0 else round(100 - (100 / (1 + avg_gain / avg_loss)), 6)

    return result


def _kdj(
    highs: list[float | None],
    lows: list[float | None],
    closes: list[float | None],
    period: int = 9,
) -> tuple[list[float | None], list[float | None]]:
    k_values: list[float | None] = []
    d_values: list[float | None] = []
    prev_k = 50.0
    prev_d = 50.0

    for index in range(len(closes)):
        close = closes[index]
        window_highs = [value for value in highs[max(0, index - period + 1) : index + 1] if value is not None]
        window_lows = [value for value in lows[max(0, index - period + 1) : index + 1] if value is not None]
        if close is None or len(window_highs) < period or len(window_lows) < period:
            k_values.append(None)
            d_values.append(None)
            continue

        highest = max(window_highs)
        lowest = min(window_lows)
        rsv = 50.0 if highest == lowest else ((close - lowest) / (highest - lowest)) * 100
        prev_k = (2 / 3) * prev_k + (1 / 3) * rsv
        prev_d = (2 / 3) * prev_d + (1 / 3) * prev_k
        k_values.append(round(prev_k, 6))
        d_values.append(round(prev_d, 6))

    return k_values, d_values
