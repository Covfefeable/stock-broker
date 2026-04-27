from datetime import date

import pytest

from app.services.market_data.adjustments import (
    _calculate_dividend_price_factors,
    _divide,
    _multiply,
    _parse_date,
)


def test_dividend_price_factor_uses_previous_trade_close() -> None:
    factors = _calculate_dividend_price_factors(
        [(date(2026, 1, 5), 2.0)],
        {
            date(2026, 1, 2): 100.0,
            date(2026, 1, 5): 98.0,
        },
    )
    assert factors == [(date(2026, 1, 5), pytest.approx(100 / 98))]


def test_dividend_factor_skips_invalid_events() -> None:
    assert _calculate_dividend_price_factors([(date(2026, 1, 1), 1.0)], {}) == []
    assert _calculate_dividend_price_factors(
        [(date(2026, 1, 2), 10.0)],
        {date(2026, 1, 1): 10.0},
    ) == []


def test_decimal_helpers_and_date_parse() -> None:
    assert _parse_date("2026-01-01") == date(2026, 1, 1)
    assert _parse_date(date(2026, 1, 1)) == date(2026, 1, 1)
    assert _divide(100, 2.5) == 40.0
    assert _multiply(100, 2.5) == 250
