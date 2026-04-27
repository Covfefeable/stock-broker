from app.services.strategies.indicators import (
    _calculate_indicators,
    _ema,
    _gap_pct,
    _range_pct,
    _simple_moving_average,
)


def make_bars(count: int = 30) -> list[dict]:
    bars = []
    for index in range(count):
        close = 100 + index
        bars.append(
            {
                "open": close - 0.5,
                "high": close + 1,
                "low": close - 1,
                "close": close,
                "volume": 1000 + index,
            }
        )
    return bars


def test_simple_moving_average_requires_full_window() -> None:
    assert _simple_moving_average([1, 2, 3, 4, 5], 3) == [None, None, 2, 3, 4]


def test_ema_uses_standard_multiplier() -> None:
    assert _ema([10, 12, 14], 3) == [10, 11, 12.5]


def test_range_pct_and_gap_pct() -> None:
    assert _range_pct([12], [8], [10]) == [0.4]
    assert _gap_pct([10, 12], [10, 11]) == [None, 0.2]


def test_calculate_indicators_key_values() -> None:
    indicators = _calculate_indicators(make_bars(30))

    assert indicators["ma5"][4] == 102
    assert indicators["ma20"][19] == 109.5
    assert indicators["range_pct"][0] == 0.02
    assert indicators["gap_pct"][1] == 0.005
    assert indicators["close_pct_of_20d_range"][19] == 0.952381
    assert indicators["distance_to_20d_high"][19] == -0.008333
    assert indicators["atr14_pct"][13] == 0.017699


def test_rsi_reaches_one_hundred_for_monotonic_rise() -> None:
    indicators = _calculate_indicators(make_bars(30))
    assert indicators["rsi14"][14] == 100.0
