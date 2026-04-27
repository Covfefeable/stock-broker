from datetime import date

from sqlalchemy import select

from app.extensions import db
from app.models.country import Country
from app.models.exchange import Exchange
from app.models.index_asset import IndexAsset
from app.models.index_daily_bar import IndexDailyBar
from app.models.stock import Stock
from app.models.stock_daily_bar import StockDailyBar
from app.models.stock_dividend import StockDividend
from app.models.stock_split import StockSplit
from app.models.trading_calendar_day import TradingCalendarDay

from app.services.data_center.constants import *  # noqa: F403
from app.services.data_center.sync_base import normalize_optional_text, parse_positive_decimal


def upsert_countries(rows: list[dict]) -> int:
    affected = 0
    for item in rows:
        country_code = str(item.get("country_code") or "").strip()
        country_name = str(item.get("country_name") or "").strip()
        if not country_code or not country_name:
            continue

        record = Country.query.filter_by(country_code=country_code).first()
        if not record:
            record = Country(country_code=country_code)
            db.session.add(record)

        record.country_name = country_name
        record.timezone = normalize_optional_text(item.get("timezone"))
        record.delay = normalize_optional_text(item.get("delay"))
        record.notes = normalize_optional_text(item.get("notes"))
        affected += 1

    db.session.commit()
    return affected


def upsert_exchanges(rows: list[dict]) -> int:
    affected = 0
    country_rows = db.session.execute(select(Country)).scalars().all()
    country_by_code = {row.country_code: row for row in country_rows}

    for item in rows:
        exchange_code = str(item.get("exchange_code") or "").strip()
        exchange_name = str(item.get("exchange_name") or "").strip()
        if not exchange_code or not exchange_name:
            continue

        record = Exchange.query.filter_by(exchange_code=exchange_code).first()
        if not record:
            record = Exchange(exchange_code=exchange_code)
            db.session.add(record)

        country_code = normalize_optional_text(item.get("country_code"))
        country = country_by_code.get(country_code) if country_code else None

        record.exchange_name = exchange_name
        record.exchange_name_short = normalize_optional_text(item.get("exchange_name_short"))
        record.country_code = country_code
        record.country_id = country.id if country else None
        record.currency_code = normalize_optional_text(item.get("currency_code"))
        record.local_open = normalize_optional_text(item.get("local_open"))
        record.local_close = normalize_optional_text(item.get("local_close"))
        record.beijing_open = normalize_optional_text(item.get("beijing_open"))
        record.beijing_close = normalize_optional_text(item.get("beijing_close"))
        record.timezone = normalize_optional_text(item.get("timezone"))
        record.delay = normalize_optional_text(item.get("delay"))
        record.notes = normalize_optional_text(item.get("notes"))
        affected += 1

    db.session.commit()
    return affected


def upsert_stocks(rows: list[dict], exchange_code: str) -> int:
    affected = 0
    exchange = Exchange.query.filter_by(exchange_code=exchange_code).first()
    country_rows = db.session.execute(select(Country)).scalars().all()
    country_by_code = {row.country_code: row for row in country_rows}

    for item in rows:
        ticker = str(item.get("ticker") or "").strip()
        name = str(item.get("name") or "").strip()
        if not ticker or not name:
            continue

        record = Stock.query.filter_by(exchange_code=exchange_code, ticker=ticker).first()
        if not record:
            record = Stock(exchange_code=exchange_code, ticker=ticker)
            db.session.add(record)

        country_code = normalize_optional_text(item.get("country_code"))
        country = country_by_code.get(country_code) if country_code else None

        record.name = name
        record.is_active = str(item.get("is_active") or "0").strip() == "1"
        record.exchange_id = exchange.id if exchange else None
        record.country_id = country.id if country else None
        record.country_code = country_code
        record.currency_code = normalize_optional_text(item.get("currency_code"))
        affected += 1

    db.session.commit()
    return affected


def upsert_index_assets(rows: list[dict], country_code: str) -> int:
    affected = 0
    country = Country.query.filter_by(country_code=country_code).first()

    for item in rows:
        ticker = str(item.get("ticker") or "").strip()
        name = str(item.get("name") or "").strip()
        if not ticker or not name:
            continue

        record = IndexAsset.query.filter_by(country_code=country_code, ticker=ticker).first()
        if not record:
            record = IndexAsset(country_code=country_code, ticker=ticker)
            db.session.add(record)

        record.name = name
        record.country_id = country.id if country else None
        affected += 1

    db.session.commit()
    return affected


def upsert_stock_daily_bars(rows: list[dict], stock: Stock) -> int:
    affected = 0
    for item in rows:
        ticker = str(item.get("ticker") or "").strip()
        trade_date_raw = str(item.get("date") or "").strip()
        if not ticker or ticker.casefold() != stock.ticker.casefold() or not trade_date_raw:
            continue

        trade_date = date.fromisoformat(trade_date_raw)
        record = StockDailyBar.query.filter_by(
            exchange_code=stock.exchange_code,
            ticker=stock.ticker,
            trade_date=trade_date,
        ).first()
        if not record:
            record = StockDailyBar(
                exchange_code=stock.exchange_code,
                ticker=stock.ticker,
                trade_date=trade_date,
            )
            db.session.add(record)

        record.stock_id = stock.id
        record.open = item.get("open")
        record.high = item.get("high")
        record.low = item.get("low")
        record.close = item.get("close")
        record.volume = int(item["volume"]) if item.get("volume") is not None else None
        affected += 1

    db.session.commit()
    return affected


def upsert_stock_splits(rows: list[dict], stock: Stock) -> int:
    affected = 0
    for item in rows:
        ticker = str(item.get("ticker") or "").strip()
        event_date_raw = str(item.get("date") or "").strip()
        split_factor = parse_positive_decimal(item.get("split_factor"))
        if (
            not ticker
            or ticker.casefold() != stock.ticker.casefold()
            or not event_date_raw
            or split_factor is None
        ):
            continue

        event_date = date.fromisoformat(event_date_raw)
        record = StockSplit.query.filter_by(
            exchange_code=stock.exchange_code,
            ticker=stock.ticker,
            event_date=event_date,
        ).first()
        if not record:
            record = StockSplit(
                exchange_code=stock.exchange_code,
                ticker=stock.ticker,
                event_date=event_date,
            )
            db.session.add(record)

        record.stock_id = stock.id
        record.split_factor = split_factor
        affected += 1

    db.session.commit()
    return affected


def upsert_stock_dividends(rows: list[dict], stock: Stock) -> int:
    affected = 0
    for item in rows:
        ticker = str(item.get("ticker") or "").strip()
        event_date_raw = str(item.get("date") or "").strip()
        dividend = parse_positive_decimal(item.get("dividend"))
        if (
            not ticker
            or ticker.casefold() != stock.ticker.casefold()
            or not event_date_raw
            or dividend is None
        ):
            continue

        event_date = date.fromisoformat(event_date_raw)
        record = StockDividend.query.filter_by(
            exchange_code=stock.exchange_code,
            ticker=stock.ticker,
            event_date=event_date,
        ).first()
        if not record:
            record = StockDividend(
                exchange_code=stock.exchange_code,
                ticker=stock.ticker,
                event_date=event_date,
            )
            db.session.add(record)

        record.stock_id = stock.id
        record.dividend = dividend
        affected += 1

    db.session.commit()
    return affected


def upsert_index_daily_bars(rows: list[dict], index_asset: IndexAsset) -> int:
    affected = 0
    for item in rows:
        ticker = str(item.get("ticker") or "").strip()
        trade_date_raw = str(item.get("date") or "").strip()
        if not ticker or ticker.casefold() != index_asset.ticker.casefold() or not trade_date_raw:
            continue

        trade_date = date.fromisoformat(trade_date_raw)
        record = IndexDailyBar.query.filter_by(
            country_code=index_asset.country_code,
            ticker=index_asset.ticker,
            trade_date=trade_date,
        ).first()
        if not record:
            record = IndexDailyBar(
                country_code=index_asset.country_code,
                ticker=index_asset.ticker,
                trade_date=trade_date,
            )
            db.session.add(record)

        record.index_asset_id = index_asset.id
        record.open = item.get("open")
        record.high = item.get("high")
        record.low = item.get("low")
        record.close = item.get("close")
        record.volume = int(item["volume"]) if item.get("volume") is not None else None
        affected += 1

    db.session.commit()
    return affected


def upsert_trading_calendar_days(rows: list[dict], exchange: Exchange) -> int:
    affected = 0
    for item in rows:
        exchange_code = str(item.get("exchange_code") or "").strip().upper()
        trade_date_raw = str(item.get("date") or "").strip()
        if not exchange_code or exchange_code != exchange.exchange_code or not trade_date_raw:
            continue

        trade_date = date.fromisoformat(trade_date_raw)
        record = TradingCalendarDay.query.filter_by(
            exchange_code=exchange.exchange_code,
            trade_date=trade_date,
        ).first()
        if not record:
            record = TradingCalendarDay(
                exchange_code=exchange.exchange_code,
                trade_date=trade_date,
            )
            db.session.add(record)

        record.exchange_id = exchange.id
        record.status = int(item.get("status") or 0)
        affected += 1

    db.session.commit()
    return affected
