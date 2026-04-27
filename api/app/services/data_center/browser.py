from sqlalchemy import func

from app.models.index_asset import IndexAsset
from app.models.index_daily_bar import IndexDailyBar
from app.models.stock import Stock
from app.models.stock_daily_bar import StockDailyBar
from app.services.market_data import apply_stock_split_adjustments

from app.services.data_center.constants import *  # noqa: F403


def get_stock_browser_bars(exchange_code: str, ticker: str) -> dict:
    normalized_exchange_code = exchange_code.strip().upper()
    normalized_ticker = ticker.strip()
    if not normalized_exchange_code or not normalized_ticker:
        return {"meta": None, "bars": []}

    stock = Stock.query.filter_by(
        exchange_code=normalized_exchange_code, ticker=normalized_ticker
    ).first()
    if not stock:
        stock = Stock.query.filter(
            Stock.exchange_code == normalized_exchange_code,
            func.lower(Stock.ticker) == normalized_ticker.lower(),
        ).first()
    if not stock:
        return {"meta": None, "bars": []}

    rows = (
        StockDailyBar.query.filter_by(exchange_code=normalized_exchange_code, ticker=stock.ticker)
        .order_by(StockDailyBar.trade_date.desc(), StockDailyBar.id.desc())
        .all()
    )
    bars = apply_stock_split_adjustments(
        [row.to_dict() for row in reversed(rows)], stock.exchange_code, stock.ticker
    )
    return {
        "meta": {
            "type": "stock",
            "name": stock.name,
            "ticker": stock.ticker,
            "exchangeCode": stock.exchange_code,
            "countryCode": stock.country_code,
            "latestDate": bars[-1]["date"] if bars else None,
            "count": len(bars),
        },
        "bars": bars,
    }


def get_index_browser_bars(country_code: str, ticker: str) -> dict:
    normalized_country_code = country_code.strip().upper()
    normalized_ticker = ticker.strip()
    if not normalized_country_code or not normalized_ticker:
        return {"meta": None, "bars": []}

    index_asset = IndexAsset.query.filter_by(
        country_code=normalized_country_code, ticker=normalized_ticker
    ).first()
    if not index_asset:
        index_asset = IndexAsset.query.filter(
            IndexAsset.country_code == normalized_country_code,
            func.lower(IndexAsset.ticker) == normalized_ticker.lower(),
        ).first()
    if not index_asset:
        return {"meta": None, "bars": []}

    rows = (
        IndexDailyBar.query.filter_by(
            country_code=normalized_country_code, ticker=index_asset.ticker
        )
        .order_by(IndexDailyBar.trade_date.desc(), IndexDailyBar.id.desc())
        .all()
    )
    bars = [row.to_dict() for row in reversed(rows)]
    return {
        "meta": {
            "type": "index",
            "name": index_asset.name,
            "ticker": index_asset.ticker,
            "countryCode": index_asset.country_code,
            "latestDate": bars[-1]["date"] if bars else None,
            "count": len(bars),
        },
        "bars": bars,
    }
