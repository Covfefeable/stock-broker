from decimal import Decimal


def format_percent(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return f"{float(value):.2f}%"


def format_score(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return f"{float(value):.2f}"


def decimal_to_float(value: Decimal | None) -> float:
    return float(value) if value is not None else 0.0
