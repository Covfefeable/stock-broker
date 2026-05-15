import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen


from app.services.data_center.constants import *  # noqa: F403


def canghai_stock_url(exchange_code: str) -> str:
    return f"https://www.tsanghi.com/api/fin/stock/{exchange_code}/list"


def canghai_etf_url(exchange_code: str) -> str:
    return f"https://www.tsanghi.com/api/fin/etf/{exchange_code}/list"


def canghai_index_url(country_code: str) -> str:
    return f"https://www.tsanghi.com/api/fin/index/{country_code}/list"


def canghai_stock_daily_url(exchange_code: str) -> str:
    return f"https://www.tsanghi.com/api/fin/stock/{exchange_code}/daily"


def canghai_etf_daily_url(exchange_code: str) -> str:
    return f"https://www.tsanghi.com/api/fin/etf/{exchange_code}/daily"


def canghai_stock_split_url(exchange_code: str) -> str:
    return f"https://www.tsanghi.com/api/fin/stock/{exchange_code}/split"


def canghai_stock_dividend_url(exchange_code: str) -> str:
    return f"https://www.tsanghi.com/api/fin/stock/{exchange_code}/dividend"


def canghai_trading_calendar_url(exchange_code: str) -> str:
    return f"https://www.tsanghi.com/api/fin/stock/{exchange_code}/market/calendar"


def canghai_index_daily_url(country_code: str) -> str:
    return f"https://www.tsanghi.com/api/fin/index/{country_code}/daily"


def build_canghai_url(base_url: str, token: str, extra_params: dict[str, str] | None = None) -> str:
    params = {"token": token, "fmt": "json"}
    if extra_params:
        params.update({key: value for key, value in extra_params.items() if value})
    return f"{base_url}?{urlencode(params)}"


def fetch_json(url: str) -> dict:
    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "stock-broker/0.1"},
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))
